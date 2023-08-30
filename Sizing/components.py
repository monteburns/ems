import pyomo.environ as pe

class Battery():

    def __init__(self):
        """ There are 100 batteries """

        self.MIN_BATTERY_CAPACITY = 0
        self.MAX_BATTERY_CAPACITY = 60e3 # kWh
        self.MAX_BATTERY_POWER = 20e3 # kW
        self.MIN_BATTERY_POWER = 0 #10e5
        self.INITIAL_CAPACITY = 40e3 # Default full initial capacity
        self.EFFICIENCY = 0.9

    def constraints(self, model, period):

        constraintlist = []
        # battery parameters
        model.charge_limit = self.MAX_BATTERY_POWER/2
        model.discharge_limit = self.MAX_BATTERY_POWER/2
        model.eff = self.EFFICIENCY

        # battery variables
        model.SOC = pe.Var(period, within=pe.NonNegativeReals, initialize = self.INITIAL_CAPACITY, bounds=[self.MIN_BATTERY_CAPACITY, self.MAX_BATTERY_CAPACITY])
       

        # Charging rate limit
        def E_charging_rate_rule(m,i):
            return m.chargeP[i]<=m.charge_limit
        model.chargingLimit_cons = pe.Constraint(period, rule=E_charging_rate_rule)
        # Discharging rate limit
        def E_discharging_rate_rule(m,i):
            return m.dischargeP[i]<=m.discharge_limit
        model.dischargingLimit_cons = pe.Constraint(period, rule=E_discharging_rate_rule)


        # Make sure the battery does not charge above the limit
        def over_charge(model, t):
            return model.chargeP[t] <= (self.MAX_BATTERY_CAPACITY - model.SOC[t])
        model.over_charge = pe.Constraint(model.T, rule=over_charge)
        constraintlist.append(model.over_charge)

        def over_discharge(model, t):
            return model.dischargeP[t] <= model.SOC[t] * model.eff 
        model.over_discharge = pe.Constraint(period, rule=over_discharge)
        constraintlist.append(model.over_discharge)

        def SOC_limit(m,t):
            return model.SOC[t] >= self.MAX_BATTERY_CAPACITY/2
        model.SOC_limit = pe.Constraint(period, rule=SOC_limit)
        constraintlist.append(model.SOC_limit)

        
        def capacity_constraint(model, t):
            # Assigning battery's starting capacity at the beginning
            if t == period.first():
                return model.SOC[t] == self.INITIAL_CAPACITY
            # if not update the capacity normally
            return model.SOC[t] == (model.SOC[t - 1]
                                           + (model.chargeP[t] * self.EFFICIENCY)
                                           - (model.dischargeP[t] / self.EFFICIENCY))
        model.SOC_constraint = pe.Constraint(period, rule=capacity_constraint)
        constraintlist.append(model.SOC_constraint)

        return constraintlist



class Hydrogen():
    """ Hydrogen system consists of SOEC based production plant,
        a storage system and a SOFC based combustion plant"""

    def __init__(self, storageCap, eff_SOEC, eff_fcell):
        self.MAX_STORAGE_CAPACITY = storageCap
        self.MIN_STORAGE_CAPACITY = 0
        self.ELECTROLYSER_POWER = 250 # kW
        self.FUEL_CELL_POWER = 10 # kW
        self.INITIAL_CAPACITY = storageCap/2 
        self.eff_SOEC = eff_SOEC
        self.eff_fcell = eff_fcell
        self.TANK_VOLUME = 4 # m3
        self.R_H2 = 4.124 # kJ/kgK
        self.TEMP = 300 # K
        self.HHV = 141.80e3/3600 # kW/kg
        self.LHV = 120e3/3600 # kW/kg

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

        #Parameters
        model.eleP = pe.Param(initialize=self.ELECTROLYSER_POWER)
        model.fcP = pe.Param(initialize=self.FUEL_CELL_POWER)
        model.tank = pe.Param(initialize=model.n_h2sys * self.TANK_VOLUME, mutable=True)
        model.storeCap = pe.Param(initialize=model.n_h2sys * self.MAX_STORAGE_CAPACITY, mutable=True)

        # Variables
        model.SOP = pe.Var(model.T, initialize= self.INITIAL_CAPACITY)

        def hydrogen_charge(model, t):
            return model.M_electrolyzer[t] == self.mdot(model.P_electrolyzer[t])
        model.hydrogenChaC = pe.Constraint(period, rule = hydrogen_charge)
        constraintlist.append(model.hydrogenChaC)

        def over_discharge(model, t):
            return model.P_fcell[t] <= self.gen((model.SOP[t] * model.tank) / (self.R_H2 * self.TEMP))
        model.discharge = pe.Constraint(period, rule=over_discharge)
        constraintlist.append(model.discharge)

        def over_charge(model, t):
            return model.P_electrolyzer[t] <= self.gen(((model.storeCap - model.SOP[t]) * model.tank) / (self.R_H2 * self.TEMP))
        model.charge = pe.Constraint(period, rule=over_charge)
        constraintlist.append(model.charge)

        def charge(model, t):
            return model.P_electrolyzer[t] <= model.P_excess[t]
        model.ChaC = pe.Constraint(period, rule = charge)
        constraintlist.append(model.ChaC)

        def electrolyser_limit(model, t):
            return model.P_electrolyzer[t] <=   model.n_h2sys * model.eleP
        model.genC = pe.Constraint(period, rule = electrolyser_limit)
        constraintlist.append(model.genC)

        def fcell_limit(model, t):
            return model.P_fcell[t] <=  model.n_h2sys * model.fcP
        model.fcellC = pe.Constraint(period, rule = fcell_limit)
        constraintlist.append(model.fcellC)

        def hydrogen_balance(model, t):

            if t == 0:
                return model.SOP[t] == model.storeCap/2
            else:
                return model.SOP[t] == model.SOP[t - 1] + (self.R_H2 * self.TEMP / model.tank) * (self.eff_SOEC * model.P_electrolyzer[t] - model.P_fcell[t] / self.eff_fcell) / self.LHV
        model.hydrogenSysC = pe.Constraint(period, rule = hydrogen_balance)
        constraintlist.append(model.hydrogenSysC)

        return constraintlist