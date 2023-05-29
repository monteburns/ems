import argparse
import pyomo.environ as pe
import platform
import matplotlib.pyplot as plt
import pandas as pd
from components import Hydrogen, Battery
from common import Data
from common import Unit


def windows():
    return platform.system() == "Windows"
def linux():
    return platform.system() == "Linux"

def main(args):

    smr = Unit()
    wind = Unit()
    solar = Unit()

    storageCap = 1000 #kg
    eff_SOEC = 0.83
    eff_fcell = 0.60

    if args.hydrogen:
        hydrogen = Hydrogen(storageCap, eff_SOEC, eff_fcell)
    
    if args.battery:
        battery = Battery()

    smr.capacity = 77000  # kW
    wind.capacity = 2000  # kW
    solar.capacity = 100  # kW

    smr.lcoe = 70.59e-3  # $/kW
    wind.lcoe = 36.93e-3  # $/kW
    solar.lcoe = 30.43e-3  # $/kW

    gen = Data()
    demand = Data()

    if windows():
        gen.filename = 'C:/Users/utae01688/Documents/Codes/ems/Sizing/Hybrid_SMR_dataset.xlsx'
        demand.filename = 'C:/Users/utae01688/Documents/Codes/ems/Sizing/Hybrid_SMR_dataset.xlsx'
    if linux():
        gen.filename = 'Hybrid_SMR_dataset.xlsx'
        demand.filename = 'Hybrid_SMR_dataset.xlsx'

    wind_p = gen.hourly('WF')
    solar_p = gen.hourly('PV')
    demand_e = demand.hourly('Demand_E')


    C = [smr.lcoe * smr.capacity, wind.lcoe * wind.capacity, solar.lcoe * solar.capacity]

    # Create a model
    model = pe.ConcreteModel()

    # Time series
    # 24-hour time period
    model.nt = pe.Param(initialize=24)
    model.T = pe.Set(initialize=range(model.nt()))

    # Assign parameter values
    model.Demand = pe.Param(model.T, initialize=demand_e)
    model.WindP = pe.Param(model.T, initialize=wind_p)
    model.SolarP = pe.Param(model.T, initialize=solar_p)


    model.smr_capacity = pe.Param(initialize=smr.capacity)
    model.wind_capacity = pe.Param(initialize=wind.capacity)
    model.solar_capacity = pe.Param(initialize=solar.capacity)

    model.P_excess = pe.Var(model.T, domain=pe.NonNegativeReals)

    if args.hydrogen:
        model.HydrogenP = pe.Var(model.T, domain=pe.NonNegativeReals)

    if args.battery:
        model.BatteryDischargeP = pe.Var(model.T, bounds=[0, battery.MAX_RAW_POWER])

    model.n_smr = pe.Var(within=pe.PositiveIntegers, initialize = 10, bounds=[1, 10])
    model.n_wind = pe.Var(within=pe.PositiveIntegers,  initialize = 10, bounds=[1, 500])
    model.n_solar = pe.Var(within=pe.PositiveIntegers, initialize = 10, bounds=[1, 1000])

    model.OBJ = pe.Objective(sense=pe.minimize, expr=C[0] * model.n_smr + C[1] * model.n_wind + C[2] * model.n_solar)

    def provide_demand(model, t):
        power_gen = [model.n_smr * smr.capacity + model.n_wind * wind.capacity * model.WindP[
            t] + model.n_solar * solar.capacity * model.SolarP[t]]
        if args.hydrogen:
            power_gen.append(model.HydrogenP[t])
        if args.battery:
            power_gen.append(model.BatteryDischargeP[t])
        return sum(power_gen) >= model.Demand[t]

    if args.battery:
        batteryCs = [cons for cons in battery.constraints(model, model.T)]

    if args.hydrogen:
        hydrogenCs = [cons for cons in hydrogen.constraints(model, model.T)]

    model.demandC = pe.Constraint(model.T, rule= provide_demand)

    # ------ solve and print out results
    # solver setup
    if windows():
        solvername='glpk'
        solverpath_folder='C:\\glpk-4.65\\w64'
        solverpath_exe='C:\\glpk-4.65\\w64\\glpsol' 
        solver = pe.SolverFactory(solvername, executable=solverpath_exe)
    if linux():
        solver = pe.SolverFactory('glpk')
    
    results = solver.solve(model, tee = True)

    model.pprint()
    results.write()
    print("Number of SMRs: ", pe.value(model.n_smr))
    print("Number of Wind turbines: ", pe.value(model.n_wind))
    print("Number of Solar panels: ", pe.value(model.n_solar))

    # Post Processing

    nuclear_gen = [pe.value(model.n_smr * smr.capacity) for t in range(24)]
    wind_gen = [pe.value(model.n_wind * wind.capacity * model.WindP[t]) for t in model.WindP]
    solar_gen = [pe.value(model.n_solar * solar.capacity * model.SolarP[t]) for t in model.SolarP]
    dict = {'Nuclear': nuclear_gen, 'Wind': wind_gen, 'Solar': solar_gen}

    if args.hydrogen:
        hydrogen_gen = [pe.value(model.HydrogenP[t]) for t in model.HydrogenP]
        dict['Hydrogen'] = hydrogen_gen
    if args.battery:
        battery_gen = [pe.value(model.BatteryDischargeP[t]) for t in model.BatteryDischargeP]
        dict['Battery'] = battery_gen

    df = pd.DataFrame(dict)

    plt.stackplot(df.index,
              [df[col] for col in df.columns],
              labels=list(dict.keys()),
              alpha=0.8)

    plt.legend(loc=2, fontsize='large')
    plt.show()

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Parameters')
    parser.add_argument("--hydrogen", action="store_true", help="Adds hydrogen system")
    parser.add_argument("--battery", action="store_true", help="Adds batteries")
        
    args = parser.parse_args()

    main(args)