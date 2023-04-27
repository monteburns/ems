import pyomo.environ as pe
import random
import matplotlib.pyplot as plt
from components import Unit
from common import Data


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('Yücehan')

    smr = Unit()
    wind = Unit()
    solar = Unit()

    smr.capacity = 77000  # kW
    wind.capacity = 2000  # kW
    solar.capacity = 100  # kW

    smr.lcoe = 70.59e-3  # $/kW
    wind.lcoe = 36.93e-3  # $/kW
    solar.lcoe = 30.43e-3  # $/kW

    gen = Data()
    demand = Data()

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

    model.n_smr = pe.Var(within=pe.PositiveIntegers, bounds=[1, 10])
    model.n_wind = pe.Var(within=pe.PositiveIntegers, bounds=[1, 50])
    model.n_solar = pe.Var(within=pe.PositiveIntegers, bounds=[1, 100])

    model.OBJ = pe.Objective(sense=pe.minimize, expr=C[0] * model.n_smr + C[1] * model.n_wind + C[2] * model.n_solar)


    # x[t] less than X_in for all t
    def provide_demand(model, t):

        return (model.n_smr * smr.capacity + model.n_wind * wind.capacity * model.WindP[
            t] + model.n_solar * solar.capacity * model.SolarP[t]) >= model.Demand[t]


    model.c_x_lim = pe.Constraint(model.T, rule=provide_demand)

    # ------ solve and print out results
    # solver setup
    solver = pe.SolverFactory('glpk')
    # solver = pyomo.SolverFactory('gurobi')
    # solver = pyomo.SolverFactory('cbc')
    solver.solve(model)

    model.pprint()

    print((6*77000*smr.lcoe + 95*2000*wind.lcoe + 35*100*solar.lcoe)/(6*77000 + 95*2000 + 35*100))
