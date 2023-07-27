import pyomo.environ as pe

class Battery():

    def __init__(self):
        """ There are 100 batteries """

        self.MIN_BATTERY_CAPACITY = 0
        self.MAX_BATTERY_CAPACITY = 580e2 
        self.MAX_BATTERY_POWER = 150e2
        self.MAX_RAW_POWER = 300e2
        self.INITIAL_CAPACITY = 0  # Default initial capacity will assume to be 0
        self.EFFICIENCY = 0.9
        self.MLF = 0.991  # Marginal Loss Factor

    def constraints(self, model, period):

        constraintlist = []
        # battery variables
        model.Capacity = pe.Var(period, bounds=[self.MIN_BATTERY_CAPACITY, self.MAX_BATTERY_CAPACITY])
        model.Charge_power = pe.Var(period, bounds=[0, self.MAX_RAW_POWER])
 
        def charge(model, t):
            model.P_excess[t] = model.n_smr * model.solar_capacity + model.n_wind * model.wind_capacity * model.WindP[
                t] + model.n_solar * model.solar_capacity * model.SolarP[t] - model.Demand[t]
            return model.Charge_power[t] <= model.P_excess[t]
        model.charge = pe.Constraint(model.T, rule=charge)
        constraintlist.append(model.charge)

        # Make sure the battery does not charge above the limit
        def over_charge(model, i):
            return model.Charge_power[i] <= (self.MAX_BATTERY_CAPACITY - model.Capacity[i]) * 2 / self.EFFICIENCY
        model.over_charge = pe.Constraint(model.T, rule=over_charge)
        constraintlist.append(model.over_charge)

        def over_discharge(model, i):
            return model.BatteryDischargeP[i] <= model.Capacity[i] * 2
        model.over_discharge = pe.Constraint(period, rule=over_discharge)
        constraintlist.append(model.over_discharge)

        def capacity_constraint(model, i):
            # Assigning battery's starting capacity at the beginning
            if i == period.first():
                return model.Capacity[i] == self.INITIAL_CAPACITY
            # if not update the capacity normally
            return model.Capacity[i] == (model.Capacity[i - 1]
                                           + (model.Charge_power[i - 1] / 2 * self.EFFICIENCY)
                                           - (model.BatteryDischargeP[i - 1] / 2))
        model.capacity_constraint = pe.Constraint(period, rule=capacity_constraint)
        constraintlist.append(model.capacity_constraint)

        return constraintlist



class Hydrogen():
    """ Hydrogen system consists of SOEC based production plant,
        a storage system and a SOFC based combustion plant"""

    def __init__(self, storageCap, eff_SOEC, eff_fcell):
        self.MAX_STORAGE_CAPACITY = storageCap
        self.MIN_STORAGE_CAPACITY = 0
        self.ELECTROLYSER_POWER = 2500e2 # kW
        self.FUEL_CELL_POWER = 100e2 # kW
        self.INITIAL_CAPACITY = 1e6 # 10 bar
        self.eff_SOEC = eff_SOEC
        self.eff_fcell = eff_fcell
        self.TANK_VOLUME = 4 # m3
        self.R_H2 = 4.124 # kJ/kgK
        self.TEMP = 300 # K
        self.HHV = 141.80e3 # kJ/kg
        self.LHV = 120e3 # kJ/kg

    def mdot(self, Pe):
        """The model assumes energy conversion based on a solid 
    oxide electrolysis cell (SOEC). Using the higher heating value 
    (HHV) of hydrogen, calculated hydrogen production rate is returned"""        
        
        return (self.eff_SOEC * Pe)/self.LHV
    
    def gen(self, mdot):
        """ hydrogen can be released from the storage and fed into the solid oxide
        fuel cell (SOFC) system to produce electricty """

        return self.eff_fcell * mdot * self.LHV

    def constraints(self, model, period):
        constraintlist = []

        model.SOP = pe.Var(period, domain=pe.NonNegativeReals, bounds=[self.MIN_STORAGE_CAPACITY, self.MAX_STORAGE_CAPACITY])
        
        def hydrogen_charge(model, t):

            model.P_excess[t] = model.n_smr * model.solar_capacity + model.n_wind * model.wind_capacity * model.WindP[
                t] + model.n_solar * model.solar_capacity * model.SolarP[t] - model.Demand[t]
            return model.P_electrolyzer[t] <= self.mdot(model.P_excess[t])
        model.hydrogenChaC = pe.Constraint(period, rule = hydrogen_charge)
        constraintlist.append(model.hydrogenChaC)

        def over_discharge(model, t):
            return model.P_fcell[t] <= self.gen((model.SOP[t] * self.TANK_VOLUME) / (self.R_H2 * self.TEMP))
        model.discharge = pe.Constraint(period, rule=over_discharge)
        constraintlist.append(model.discharge)

        def electrolyser_limit(model, t):
            return model.P_electrolyzer[t] <= self.ELECTROLYSER_POWER
        model.genC = pe.Constraint(period, rule = electrolyser_limit)
        constraintlist.append(model.genC)

        def fcell_limit(model, t):
            return model.P_fcell[t] <= self.FUEL_CELL_POWER
        model.fcellC = pe.Constraint(period, rule = fcell_limit)
        constraintlist.append(model.fcellC)

        def hydrogen_balance(model, t):

            if t == 0:
                return model.SOP[t] == self.INITIAL_CAPACITY
            else:
                return model.SOP[t] == model.SOP[t - 1] + (self.R_H2 * self.TEMP / self.TANK_VOLUME) * (self.eff_SOEC * model.P_electrolyzer[t] - model.P_fcell[t] / self.eff_fcell) / self.LHV
            
        model.hydrogenSysC = pe.Constraint(period, rule = hydrogen_balance)
        constraintlist.append(model.hydrogenSysC)

        return constraintlist