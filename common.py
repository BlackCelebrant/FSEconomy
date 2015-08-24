import pandas as pd
import pickle

import const


def load_pickled_assignments():
    with open('assignments', 'rb') as f:
        assignments = pickle.load(f)
    assignments.Pay = assignments.Pay.astype(float)
    assignments.Amount = assignments.Amount.astype(float)
    assignments['All-In'] = assignments['All-In'].map(lambda x: True if x == 'true' else False)
    assignments.PtAssignment = assignments.PtAssignment.map(lambda x: True if x == 'true' else False)
    return assignments

def load_airports():
    airports = pd.read_csv(const.AIRPORTS_FILENAME)
    airports.lat = airports.lat.astype(float)
    airports.lon = airports.lon.astype(float)
    return airports

def load_aircrafts():
    aircrafts = pd.read_csv(const.AIRCRAFTS_FILENAME)
    aircrafts.columns = ['Model', 'Crew', 'Seats', 'Cruise', 'Ext1', 'LTip', 'LAux', 'LMain', 'Center', 'Center2',
                         'Center3', 'RMain', 'RAux', 'RTip', 'Ext2', 'GPH', 'FuelType', 'MTOW', 'EmptyWeight', 'Price']
    aircrafts.Seats = aircrafts.Seats.astype(int)
    aircrafts.Crew = aircrafts.Crew.astype(int)
    aircrafts.Cruise = aircrafts.Cruise.astype(float)
    return aircrafts
