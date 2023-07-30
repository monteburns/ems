import argparse
import pyomo.environ as pe
import matplotlib.pyplot as plt
import pandas as pd
from components import Hydrogen, Battery
from common import Data, Unit
import os, sys


def main(args):

    smr = Unit()
    wind = Unit()
    solar = Unit()

    storageCap = 3e6 # 30 bar
    eff_SOEC = 0.83
    eff_fcell = 0.60

    if args.hydrogen:
        hydrogen = Hydrogen(storageCap, eff_SOEC, eff_fcell)
    
    if args.battery:
        battery = Battery()

    smr.capacity = 77000  # kW
    wind.capacity = 2000  # kW
    solar.capacity = 1  # kW

    smr.lcoe = 64.00e-3  # $/kW
    wind.lcoe = 36.93e-3  # $/kW
    solar.lcoe = 30.43e-3  # $/kW

    gen = Data()
    demand = Data()

    geb = Data()

    gen.filename = 'Hybrid_SMR_dataset.xlsx'
    demand.filename = 'Hybrid_SMR_dataset.xlsx'

    
    
    wind_p = gen.hourly('WF')
    solar_p = gen.hourly('PV')
    demand_e = demand.hourly('Demand_E')

    # Hourly demand profile taken from a day in GEBZE OSB
    geb.filename = 'tuk1.xlsx'
    dem_geb = geb.hourly('Demand')
    normlist = geb.profile(dem_geb)

    # example for a daily demand in 24.07.2023 
    demand_e =  [hour * 5306586 for hour in normlist]


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

    model.P_excess = pe.Var(model.T, domain=pe.Reals)

    if args.hydrogen:
        model.P_electrolyzer = pe.Var(model.T, domain=pe.NonNegativeReals)
        model.P_fcell = pe.Var(model.T, domain=pe.NonNegativeReals)

    if args.battery:
        model.BatteryDischargeP = pe.Var(model.T, bounds=[0, battery.MAX_RAW_POWER])

    model.n_smr = pe.Var(within=pe.PositiveIntegers, initialize = 10, bounds=[1, 10])
    model.n_wind = pe.Var(within=pe.PositiveIntegers,  initialize = 10, bounds=[1, 500])
    model.n_solar = pe.Var(within=pe.PositiveIntegers, initialize = 10, bounds=[1, 100000])

    model.OBJ = pe.Objective(sense=pe.minimize, expr=C[0] * model.n_smr + C[1] * model.n_wind + C[2] * model.n_solar)

    def provide_demand(model, t):
        power_gen = [model.n_smr * smr.capacity + model.n_wind * wind.capacity * model.WindP[
            t] + model.n_solar * solar.capacity * model.SolarP[t]]
        if args.hydrogen:
            power_gen.append(model.P_fcell[t])
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
        hydrogen_gen = [pe.value(model.P_fcell[t]) for t in model.P_fcell]
        dict['Hydrogen'] = hydrogen_gen
    if args.battery:
        battery_gen = [pe.value(model.BatteryDischargeP[t]) for t in model.BatteryDischargeP]
        dict['Battery'] = battery_gen

    df = pd.DataFrame(dict)


    # print LCOE 

    lcoe_sys = (smr.lcoe * sum(nuclear_gen) + wind.lcoe * sum(wind_gen) + solar.lcoe * sum(solar_gen)) / (sum(nuclear_gen) + sum(wind_gen) + sum(solar_gen) + sum(hydrogen_gen))

    print("System LCOE: %5.2f $/kW" % (1e3* lcoe_sys))


    # Show graphs

    plt1 = df.plot(kind='bar', stacked=True, title='Daily Generation')
    plt1.plot(demand_e)
    plt.show()


if __name__ == '__main__':

    workingDirectory  = os.path.realpath(sys.argv[0])

    parser = argparse.ArgumentParser(description='Parameters')
    parser.add_argument("--hydrogen", action="store_true", help="Adds hydrogen system")
    parser.add_argument("--battery", action="store_true", help="Adds batteries")
        
    args = parser.parse_args()

    main(args)