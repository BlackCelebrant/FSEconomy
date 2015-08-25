import pandas as pd
import pickle
from math import atan2, cos, pow, sin, sqrt

import const


get_ratio_func = lambda x: round(x['Earnings'] / ((x['Distance'] + x['CraftDistance']) / x['CraftCruise']), 2)


def get_best_assignments(x, df):
    df = df[(df.FromIcao == x['FromIcao']) & (df.ToIcao == x['ToIcao']) & (df.Amount <= x['CraftSeats'])]
    import pdb; pdb.set_trace()
    df['PayPerUnit'] = df.apply(lambda y: round(y['Pay'] / y['Amount'], 2), axis=1)
    df = df.sort('PayPerUnit')
    indexes = []
    current_amount = 0
    for index, row in df.iterrows():
        if current_amount + row['Amount'] > x['CraftSeats']:
            break
        current_amount += row['Amount']
        indexes.append(index)
    return indexes

    t = {}                                     #
    #for i in range(0, len(a)):
    #    t[float(a[i]) / float(c[i])] = i
    #k = t.keys()
    #k.sort()
    #c_greedy = 0
    #w_greedy = 0
    #for i in k:
    #    if w_greedy + a[t[i]] <= b:
    #        w_greedy = w_greedy + a[t[i]]
    #        c_greedy = c_greedy + c[t[i]]

    #c_max=max(c)

    #c_result = max(c_greedy, c_max)
    ## TODO: return vector with assignments ids
    #return c_result


def get_distance(lat1, lon1, lat2, lon2):
    r = 6371000
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = pow(sin(dlat/2), 2) + cos(lat1) * cos(lat2) * pow(sin(dlon/2), 2)
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return round((r * c) / 1850, 1)


def get_earnings(x, rent_column):
    res = x['Pay'] / x['Amount'] * min(x['CraftSeats'], x['Amount'])  # dirty earnings
    try:
        if x['PtAssignment'] > 6:
            res -= res * x['PtAssignment'] / 100                          # booking fee
    except:
        import pdb; pdb.set_trace()
    return round(res - x[rent_column], 2) if x[rent_column] else 0


def get_ratio(x, earnings_column):
    return round(x[earnings_column] / ((x['Distance'] + x['CraftDistance']) / x['CraftCruise']), 2)


def get_rent(x, rental_column):
    return round((x['Distance'] + x['CraftDistance']) * x[rental_column] / x['CraftCruise'], 2)


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
