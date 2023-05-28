import pyomo.environ as pe

class Battery():

    def constraints(self, model, period):
        MIN_BATTERY_CAPACITY = 0
        MAX_BATTERY_CAPACITY = 580
        MAX_BATTERY_POWER = 150
        MAX_RAW_POWER = 300
        INITIAL_CAPACITY = 0  # Default initial capacity will assume to be 0
        EFFICIENCY = 0.9
        MLF = 0.991  # Marginal Loss Factor
        constraintlist = []
        # battery variables
        model.Capacity = pe.Var(period, bounds=[MIN_BATTERY_CAPACITY, MAX_BATTERY_CAPACITY])
        model.Charge_power = pe.Var(period, bounds=[0, MAX_RAW_POWER])
        # model.Discharge_power = pe.Var(period, bounds=[0, MAX_RAW_POWER])

        # model.P_excess = pe.Var(period, domain=pe.NonNegativeReals)

        def charge(model, t):
            model.P_excess[t] = model.n_smr * model.solar_capacity + model.n_wind * model.wind_capacity * model.WindP[
                t] + model.n_solar * model.solar_capacity * model.SolarP[t] - model.Demand[t]
            return model.Charge_power[t] <= model.P_excess[t]
        model.charge = pe.Constraint(model.T, rule=charge)
        constraintlist.append(model.charge)
        # Make sure the battery does not charge above the limit
        def over_charge(model, i):
            return model.Charge_power[i] <= (MAX_BATTERY_CAPACITY - model.Capacity[i]) * 2 / EFFICIENCY

        model.over_charge = pe.Constraint(model.T, rule=over_charge)
        constraintlist.append(model.over_charge)

        def over_discharge(model, i):
            return model.Discharge_power[i] <= model.Capacity[i] * 2

        model.over_discharge = pe.Constraint(period, rule=over_discharge)
        constraintlist.append(model.over_discharge)
        def capacity_constraint(model, i):
            # Assigning battery's starting capacity at the beginning
            if i == period.first():
                return model.Capacity[i] == INITIAL_CAPACITY
            # if not update the capacity normally
            return model.Capacity[i] == (model.Capacity[i - 1]
                                           + (model.Charge_power[i - 1] / 2 * EFFICIENCY)
                                           - (model.Discharge_power[i - 1] / 2))

        model.capacity_constraint = pe.Constraint(period, rule=capacity_constraint)
        constraintlist.append(model.capacity_constraint)

        return constraintlist



class Hydrogen():
    """ Hydrogen system consists of SOEC based production plant,
        a storage system and a SOFC based combustion plant"""

    def __init__(self, storageCap, eff_SOEC, eff_fcell):
        self.storageCap = storageCap
        self.eff_SOEC = eff_SOEC
        self.eff_fcell = eff_fcell
        self.HHV = 141.80e3 # kJ/kg

    def mdot(self, Pe):
        """The model assumes energy conversion based on a solid 
    oxide electrolysis cell (SOEC). Using the higher heating value 
    (HHV) of hydrogen, calculated hydrogen production rate is returned"""        
        
        return (self.eff_SOEC * Pe)/self.HHV
    
    def gen(self, mdot):
        """ hydrogen can be released from the storage and fed into the solid oxide
        fuel cell (SOFC) system to produce electricty """

        return self.eff_fcell * mdot * self.HHV

    def constraints(self, model, period):
        constraintlist = []

        model.hydrogenCap = pe.Param(initialize=self.storageCap)
        model.hydrogen_hourly_cap = pe.Param(initialize=1)
        model.hydrogen_initial_store = pe.Param(initialize=10)

        model.hydrogen_charge = pe.Var(period, domain=pe.NonNegativeReals)
        model.hydrogenStore = pe.Var(period, domain=pe.NonNegativeReals, initialize=model.hydrogen_initial_store,
                                     bounds=[1, self.storageCap])

        # model.HydrogenP = pe.Var(period, domain=pe.NonNegativeReals)
        # model.P_excess = pe.Var(period, domain=pe.NonNegativeReals)
        def hydrogen_power(model, t):

            return model.HydrogenP[t] <= self.gen(model.hydrogen_hourly_cap)  # 1 kg a 85000 kW uretiyor
        model.hydrogenPowC = pe.Constraint(period, rule = hydrogen_power)
        constraintlist.append(model.hydrogenPowC)
        def hydrogen_storage(model, t):

            return model.hydrogenStore[t] >= model.hydrogen_hourly_cap
        model.hydrogenStoreC = pe.Constraint(period, rule = hydrogen_storage)
        constraintlist.append(model.hydrogenStoreC)
        def hydrogen_charge(model, t):

            model.P_excess[t] = model.n_smr * model.solar_capacity + model.n_wind * model.wind_capacity * model.WindP[
                t] + model.n_solar * model.solar_capacity * model.SolarP[t] - model.Demand[t]
            return model.hydrogen_charge[t] <= self.mdot(model.P_excess[t])
        model.hydrogenChaC = pe.Constraint(period, rule = hydrogen_charge)
        constraintlist.append(model.hydrogenChaC)
        def hydrogen_balance(model, t):

            if t == 0:
                return model.hydrogenStore[t] == model.hydrogen_initial_store
            else:
                return model.hydrogenStore[t] == model.hydrogenStore[t - 1] + model.hydrogen_charge[t] - self.mdot(
                    model.HydrogenP[t])
        model.hydrogenSysC = pe.Constraint(period, rule = hydrogen_balance)
        constraintlist.append(model.hydrogenSysC)

        return constraintlist