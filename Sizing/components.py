


class Unit():

    def __int__(self, capacity, eff, lcoe):
        self.capacity = capacity
        self.eff = eff
        self.lcoe = lcoe

class Battery():

    def __int__(self, capacity):
        self.capacity = capacity

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

    