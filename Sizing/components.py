


class Unit():

    def __int__(self, capacity, eff, lcoe):
        self.capacity = capacity
        self.eff = eff
        self.lcoe = lcoe

class Battery():

    def __int__(self, capacity):
        self.capacity = capacity

class Hydrogen():

    def __init__(self, capacity, eff):
        self.storageCap = capacity
        self.eff = eff

    def mdot(self, Pe):
        """The model assumes energy conversion based on a solid 
    oxide electrolysis cell (SOEC). Using the higher heating value 
    (HHV) of hydrogen, calculated hydrogen production rate is returned"""
        HHV = 141.80e3 # kJ/kg
        
        return (self.eff * Pe)/HHV
    