import pandas as pd

class Unit():

    def __int__(self, capacity, eff, lcoe):
        self.capacity = capacity
        self.eff = eff
        self.lcoe = lcoe
class Data():

    def __int__(self, filename):
        self.filename = filename

    @staticmethod
    def read(filename):
        df = pd.read_csv(filename)

        return df

    def daily(self, parameter):
        df = self.read(self.filename)

        return df[parameter].tolist()

    hourly = daily

    def profile(self, demandlist):
        """Normizing according to sum since norm hour value will be 
        multiplied by daily total consumption"""

        normlist = [float(i)/sum(demandlist) for i in demandlist]

        return normlist






