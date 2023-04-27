import pandas as pd

class Data():

    def __int__(self, filename):
        self.filename = filename

    @staticmethod
    def read(filename):
        df = pd.read_excel(filename)

        return df

    def hourly(self, parameter):
        df = self.read(self.filename)

        return df[parameter].tolist()







