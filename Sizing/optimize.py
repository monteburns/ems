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

    if args.hydrogen:
        storageCap = 3e6 #3e6 # 30 bar
        eff_SOEC = 0.83
        eff_fcell = 0.60
        hydrogen = Hydrogen(storageCap, eff_SOEC, eff_fcell)
    
    if args.battery:
        battery = Battery()

    smr.capacity = 77000  # kW
    wind.capacity = 2000  # kW
    solar.capacity = 1 # kW

    smr.lcoe = 64.00e-3  # $/kW
    wind.lcoe = 36.93e-3  # $/kW
    solar.lcoe = 30.43e-3  # $/kW

    gridPrice = 0.14 # $/kW
    batterylcoe = 0.1 # (0.15) $/kW
    fcprice = 0.2
    h2price = 8  

    profile = Data()
    demand = Data()
    rpg = Data()

    demand.filename = 'COSB_daily.csv'
    rpg.filename = 'RPG.csv'
    
    wind_p = rpg.hourly('wind')
    solar_p = rpg.hourly('solar')

    windP = [i * wind.capacity for i in wind_p]
    solarP = [i * solar.capacity for i in solar_p]

    # Hourly demand profile taken from a day in GEBZE OSB
    profile.filename = 'tuk1.csv'

    profileList = profile.hourly('Demand')
    normlist = profile.profile(profileList)

    demand_daily = demand.daily('Demand')

    demand_aday, demand_hourly = [], []
    for aday in demand_daily:
        demand_aday =  [hour * aday for hour in normlist]
        demand_hourly.extend(demand_aday)


    C = [smr.lcoe * smr.capacity, wind.lcoe * wind.capacity, solar.lcoe * solar.capacity]

    # Create a model
    model = pe.ConcreteModel()

    # Time series
    model.nt = pe.Param(initialize=len(demand_hourly))
    model.T = pe.Set(initialize=range(model.nt()))

    # Assign parameter values
    model.Demand = pe.Param(model.T, initialize=demand_hourly)
    model.WindP = pe.Param(model.T, initialize=windP)
    model.SolarP = pe.Param(model.T, initialize=solarP)
    model.smrP = pe.Param(initialize=smr.capacity)

    model.P_excess = pe.Var(model.T, domain=pe.Reals)
    # model.power_gen = pe.Var(model.T, domain=pe.NonNegativeReals)

    if args.hydrogen:
        model.P_electrolyzer = pe.Var(model.T, initialize=0, domain=pe.NonNegativeReals)
        model.M_electrolyzer = pe.Var(model.T, initialize=0, domain=pe.NonNegativeReals)
        model.P_fcell = pe.Var(model.T, initialize=0, domain=pe.NonNegativeReals)
    

    if args.battery:
        model.chargeP = pe.Var(model.T, initialize=0, domain=pe.NonNegativeReals)
        model.dischargeP = pe.Var(model.T, initialize=0, domain=pe.NonNegativeReals)

    model.n_smr = pe.Var(within=pe.PositiveIntegers, initialize = 1, bounds=[1, 5])
    model.n_wind = pe.Var(within=pe.PositiveIntegers,  initialize = 10, bounds=[1, 100])
    model.n_solar = pe.Var(within=pe.PositiveIntegers, initialize = 1000, bounds=[100, 200000])

    model.n_h2sys = pe.Param(initialize=100)

    gridpower = 40000
    model.Pgrid = pe.Var(model.T, initialize=0, bounds=[0,gridpower])

    def objFunc(model): 
        return sum((smr.lcoe * model.n_smr* model.smrP) + (wind.lcoe*model.n_wind*model.WindP[t]) + (solar.lcoe*model.n_solar*model.SolarP[t]
            + (gridPrice * model.Pgrid[t]) + (batterylcoe * model.dischargeP[t]) + (fcprice * model.P_fcell[t]) - (h2price * model.M_electrolyzer[t])) for t in model.T)  

    model.OBJ = pe.Objective(sense=pe.minimize, expr=objFunc)


    if args.battery and not args.hydrogen:
        def provide_demand(model, t):
            return (model.n_smr * model.smrP + model.n_wind * model.WindP[t] + model.n_solar * model.SolarP[t] + 
                model.dischargeP[t] - model.chargeP[t] + model.Pgrid[t]) >= model.Demand[t]
        batteryCs = [cons for cons in battery.constraints(model, model.T)]


    elif args.hydrogen and args.battery:
        def provide_demand(model, t):
            return (model.n_smr * model.smrP + model.n_wind * model.WindP[t] + model.n_solar * model.SolarP[t] + 
                model.dischargeP[t] - model.chargeP[t] + model.Pgrid[t] + model.P_fcell[t] - model.P_electrolyzer[t]) >= model.Demand[t]
        hydrogenCs = [cons for cons in hydrogen.constraints(model, model.T)]
        batteryCs = [cons for cons in battery.constraints(model, model.T)]

    else:
        def provide_demand(model, t):
            return (model.n_smr * model.smrP + model.n_wind * model.WindP[t] + model.n_solar * model.SolarP[t]) >= model.Demand[t]

    def p_excess(model,t):
        return model.P_excess[t] == model.n_smr * model.smrP + model.n_wind * model.WindP[t] + model.n_solar * model.SolarP[t] + model.dischargeP[t] - model.chargeP[t] + model.Pgrid[t] + model.P_fcell[t] -model.P_electrolyzer[t] - model.Demand[t]
    model.pexcesC = pe.Constraint(model.T, rule= p_excess)


    model.demandC = pe.Constraint(model.T, rule= provide_demand)

    # ------ solve and print out results
    # solver setup
    solver = pe.SolverFactory('glpk')
    
    results = solver.solve(model, tee = True)

    # model.pprint()

    # model.P_fcell.pprint()
    # model.P_electrolyzer.pprint()
    # model.M_electrolyzer.pprint()
    # model.SOP.pprint()

    results.write()

    print("Number of SMRs: ", pe.value(model.n_smr))
    print("Number of Wind turbines: ", pe.value(model.n_wind))
    print("Number of Solar panels: ", pe.value(model.n_solar))


    # Post Processing
    nuclear_gen = [pe.value(model.n_smr * smr.capacity) for t in range(model.nt())]
    wind_gen = [pe.value(model.n_wind * model.WindP[t]) for t in model.WindP]
    solar_gen = [pe.value(model.n_solar * model.SolarP[t]) for t in model.SolarP]

    grid_gen = [pe.value(model.Pgrid[t]) for t in model.Pgrid ]
    hydrogen_gen = [pe.value(model.P_fcell[t]) for t in model.P_fcell]
    battery_gen = [pe.value(model.dischargeP[t]) for t in model.dischargeP]
    power_gen = [(nuclear_gen[t] + wind_gen[t] + solar_gen[t] + grid_gen[t] + battery_gen[t]) for t in range(model.nt())]

    dict = {'Nuclear': nuclear_gen, 'Wind': wind_gen, 'Solar': solar_gen,'Grid':grid_gen, 'TotalGEN': power_gen, 'Demand': demand_hourly}

    if args.hydrogen:
        hydrogen_gen = [pe.value(model.P_fcell[t]) for t in model.P_fcell]
        m_electrolyzer = [pe.value(model.M_electrolyzer[t]) for t in model.M_electrolyzer]
        p_electrolyzer = [pe.value(model.M_electrolyzer[t]) for t in model.P_electrolyzer]
        tank = [pe.value(model.SOP[t]) for t in model.SOP]
        dict['Hydrogen'] = hydrogen_gen
        dict['M_Electrolyzer'] = m_electrolyzer
        dict['P_Electrolyzer'] = p_electrolyzer
        dict['SOP'] = tank
    if args.battery:
        batteryDischarge = [pe.value(model.dischargeP[t]) for t in model.dischargeP]
        batteryCharge = [pe.value(model.chargeP[t]) for t in model.chargeP]
        batteryCapacity = [pe.value(model.SOC[t]) for t in model.SOC]
        dict['Battery Power'] = batteryDischarge
        dict['Battery Charge'] = batteryCharge
        dict['SOC'] = batteryCapacity

    df = pd.DataFrame(dict)

    lcoe_sys = (smr.lcoe * sum(nuclear_gen) + wind.lcoe * sum(wind_gen) + solar.lcoe * sum(solar_gen) + gridPrice * sum(grid_gen) 
        + sum(battery_gen) - h2price * sum(m_electrolyzer)) / sum(power_gen)
    lcoe_woH2 = (smr.lcoe * sum(nuclear_gen) + wind.lcoe * sum(wind_gen) + solar.lcoe * sum(solar_gen) + gridPrice * sum(grid_gen) 
        + sum(battery_gen)) / sum(power_gen)

    print("System LCOE: %5.2f $/MW" % (1e3* lcoe_sys))
    print("LCOE without Hydrogen: %5.2f $/MW" % (1e3* lcoe_woH2))
    print("Total Hydrogen generated: %5.2f kg" % (sum(m_electrolyzer)))

    # Show graphs
    if args.horizon and args.battery:

        df[['Nuclear','Wind','Solar','Grid', 'Battery Power']].iloc[100:125].plot(kind='bar', stacked=True, figsize=(16,8))
        plt.plot(demand_hourly[100:125], label = 'Demand')
        # plt.show()

    if args.bstate and args.battery:

        df[['BatteryCharge', 'Battery', 'BattCapacity']].plot(figsize=(12, 4), subplots=True)
        

    if args.subplots:  

        if args.battery and not args.hydrogen:
            subplots = df[['Nuclear','Wind','Solar','Grid', 'Battery Power','Battery Charge', 'SOC','TotalGEN','Demand']].plot(figsize=(12, 4), 
                subplots=True, grid=True)
            subplots[6].set_ylim(bottom=0)
            fig, ax = plt.subplots()
            labels = 'Nuclear','Wind', 'Solar', 'Grid', 'Battery'
            explode = [0, 0, 0, 0.1, 0.2]
            patches, texts, autotexts = ax.pie([sum(nuclear_gen), sum(wind_gen), sum(solar_gen), sum(grid_gen), sum(battery_gen)],  
                labels=labels, autopct='%1.1f%%', labeldistance=1.2, explode=explode)
        elif args.hydrogen and args.battery:
            subplots = df[['Nuclear','Wind','Solar','Grid', 'Battery Power','Battery Charge', 'SOC','TotalGEN','P_Electrolyzer','Demand']].plot(figsize=(12, 4), 
                subplots=True, grid=True)
            fig, ax = plt.subplots()
            labels = 'Nuclear','Wind', 'Solar', 'Grid', 'Battery'
            explode = [0, 0, 0, 0.1, 0.2]
            patches, texts, autotexts = ax.pie([sum(nuclear_gen), sum(wind_gen), sum(solar_gen), sum(grid_gen), sum(battery_gen)],  
                labels=labels, autopct='%1.1f%%', labeldistance=1.2, explode=explode)
            df[['Hydrogen', 'M_Electrolyzer','SOP']].plot(figsize=(12, 4), subplots=True)
        elif args.hydrogen and not args.battery:
            pass

        else:
            df[['Nuclear','Wind','Solar','TotalGEN','Demand']].plot.area(figsize=(12, 4), subplots=True)

    # plt.legend(loc='upper left')
    plt.tight_layout()
    plt.xlabel('Hour')
    # plt.ylabel('kW')
    plt.show()


if __name__ == '__main__':

    workingDirectory  = os.path.realpath(sys.argv[0])

    parser = argparse.ArgumentParser(description='Parameters')
    parser.add_argument("--hydrogen", action="store_true", help="Adds hydrogen system")
    parser.add_argument("--battery", action="store_true", help="Adds batteries")
    parser.add_argument("--horizon", action="store_true", help="Show graphs")
    parser.add_argument("--bstate", action="store_true", help="Show graphs")
    parser.add_argument("--subplots", action="store_true", help="Show graphs")
        
    args = parser.parse_args()

    main(args)