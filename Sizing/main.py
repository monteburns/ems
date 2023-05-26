import pyomo.environ as pe
import platform
import matplotlib.pyplot as plt
from components import Unit
from components import Hydrogen
from common import Data


def windows():
    return platform.system() == "Windows"
def linux():
    return platform.system() == "Linux"

if __name__ == '__main__':

    smr = Unit()
    wind = Unit()
    solar = Unit()

    storageCap = 1000 #kg
    eff_SOEC = 0.83
    eff_fcell = 0.60

    hydrogen = Hydrogen(storageCap, eff_SOEC, eff_fcell)

    smr.capacity = 77000  # kW
    wind.capacity = 2000  # kW
    solar.capacity = 100  # kW
    

    smr.lcoe = 70.59e-3  # $/kW
    wind.lcoe = 36.93e-3  # $/kW
    solar.lcoe = 30.43e-3  # $/kW

    gen = Data()
    demand = Data()

    if (windows()):
        gen.filename = 'C:/Users/utae01688/Documents/Codes/ems/Sizing/Hybrid_SMR_dataset.xlsx'
        demand.filename = 'C:/Users/utae01688/Documents/Codes/ems/Sizing/Hybrid_SMR_dataset.xlsx'
    if (linux()):
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
    model.hydrogenCap = pe.Param(initialize = hydrogen.storageCap)
    model.hydrogen_hourly_cap = pe.Param(initialize = 1)
    model.hydrogen_initial_store = pe.Param(initialize = 10)
    

    model.n_smr = pe.Var(within=pe.PositiveIntegers, initialize = 1, bounds=[1, 10])
    model.n_wind = pe.Var(within=pe.PositiveIntegers,  initialize = 1, bounds=[1, 50])
    model.n_solar = pe.Var(within=pe.PositiveIntegers, initialize = 1, bounds=[1, 100])

    model.hydrogen_charge = pe.Var(model.T, domain = pe.NonNegativeReals)
    model.hydrogenStore = pe.Var(model.T, domain = pe.NonNegativeReals, initialize = model.hydrogen_initial_store, bounds=[1, hydrogen.storageCap])

    model.HydrogenP = pe.Var(model.T, domain = pe.NonNegativeReals)
    model.P_excess = pe.Var(model.T, domain = pe.NonNegativeReals)

    model.OBJ = pe.Objective(sense=pe.minimize, expr=C[0] * model.n_smr + C[1] * model.n_wind + C[2] * model.n_solar)

 
    def provide_demand(model, t):

        return (model.n_smr * smr.capacity + model.n_wind * wind.capacity * model.WindP[
            t] + model.n_solar * solar.capacity * model.SolarP[t] + model.HydrogenP[t])  >= model.Demand[t]
    
    def hydrogen_power(model, t):
        
        return model.HydrogenP[t] <= hydrogen.gen(model.hydrogen_hourly_cap) #1 kg a 85000 kW uretiyor
        
    def hydrogen_storage(model, t):

        return model.hydrogenStore[t] >= model.hydrogen_hourly_cap

    def hydrogen_charge(model, t):

        model.P_excess[t] = model.n_smr * smr.capacity + model.n_wind * wind.capacity * model.WindP[t] + model.n_solar * solar.capacity * model.SolarP[t] - model.Demand[t]
        return model.hydrogen_charge[t] == hydrogen.mdot(model.P_excess[t])
    
    def hydrogen_balance(model, t):

        if t==0:
            return model.hydrogenStore[t] == model.hydrogen_initial_store
        else:
            return model.hydrogenStore[t] == model.hydrogenStore[t-1] + model.hydrogen_charge[t] - hydrogen.mdot(model.HydrogenP[t])
        

    model.demandC = pe.Constraint(model.T, rule= provide_demand)
    model.hydrogenPowC = pe.Constraint(model.T, rule = hydrogen_power)
    model.hydrogenStoreC = pe.Constraint(model.T, rule = hydrogen_storage)
    model.hydrogenChaC = pe.Constraint(model.T, rule = hydrogen_charge)
    model.hydrogenSysC = pe.Constraint(model.T, rule = hydrogen_balance)
    

    # ------ solve and print out results
    # solver setup
    if (windows()):
        solvername='glpk'
        solverpath_folder='C:\\glpk-4.65\\w64'
        solverpath_exe='C:\\glpk-4.65\\w64\\glpsol' 
        solver = pe.SolverFactory(solvername,executable=solverpath_exe)
    if (linux()):
        solver = pe.SolverFactory('glpk')
    
    results = solver.solve(model, tee = True)

    model.pprint()
    results.write()