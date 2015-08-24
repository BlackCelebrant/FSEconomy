import argparse
import pandas as pd
import pickle
import time
import urllib2
import numpy as np
from math import atan2, cos, pow, radians, sin, sqrt
from StringIO import StringIO

import common
import const


class FSEconomy(object):
    def __init__(self, local, user_key=None, service_key=None):
        self.airports = common.load_airports()
        self.aircrafts = common.load_aircrafts()
        self.last_request_time = time.time()
        self.service_key = service_key
        self.user_key = user_key
        if local:
            self.assignments = common.load_pickled_assignments()
        else:
            self.assignments = self.get_assignments()

    def get_aircrafts_by_icao(self, icao):
        data = self.get_query(const.LINK + 'query=icao&search=aircraft&icao={}'.format(icao))
        aircrafts = pd.DataFrame.from_csv(StringIO(data))
        try:
            aircrafts.RentalDry = aircrafts.RentalDry.astype(float)
            aircrafts.RentalWet = aircrafts.RentalWet.astype(float)
        except Exception as err:
            import pdb; pdb.set_trace()
        return aircrafts

    def get_assignments(self):
        assignments = pd.DataFrame()

        i = 0
        while i+1500 < len(self.airports):
            data = StringIO(self.get_jobs_from(self.airports.icao[i:i+1500]))
            assignments = pd.concat([assignments, pd.DataFrame.from_csv(data)])
            i += 1500
            print i
        data = StringIO(self.get_jobs_from(self.airports.icao[i:len(self.airports)-1]))
        assignments = pd.concat([assignments, pd.DataFrame.from_csv(data)])
        with open('assignments', 'wb') as f:
            pickle.dump(assignments, f)
        return assignments

    def get_jobs_from(self, icaos):
        return self.get_query(const.LINK + 'query=icao&search=jobsfrom&icaos={}'.format('-'.join(icaos)))

    def get_closest_airports(self, icao, nm):
        lat = self.airports[self.airports.icao == icao].lat.iloc[0]
        nm = float(nm)
        # one degree of latitude is appr. 69 nm
        lat_min = lat - nm / 69
        lat_max = lat + nm / 69
        filtered_airports = self.airports[self.airports.lat > lat_min]
        filtered_airports = filtered_airports[filtered_airports.lat < lat_max]
        distance_vector = filtered_airports.icao.map(lambda x: self.get_distance(icao, x))
        return filtered_airports[distance_vector < nm]

    def get_distance(self, from_icao, to_icao):
        lat1 = radians(self.airports[self.airports.icao == from_icao]['lat'].iloc[0])
        lon1 = radians(self.airports[self.airports.icao == from_icao]['lon'].iloc[0])
        lat2 = radians(self.airports[self.airports.icao == to_icao]['lat'].iloc[0])
        lon2 = radians(self.airports[self.airports.icao == to_icao]['lon'].iloc[0])
        R = 6371000
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = pow(sin(dlat/2), 2) + cos(lat1) * cos(lat2) * pow(sin(dlon/2), 2)
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return round((R * c) / 1850, 1)

    def get_query(self, query_link):
        if self.user_key:
            query_link += '&userkey={}'.format(self.user_key)
        elif self.service_key:
            query_link += '&servicekey={}'.format(self.service_key)
        while time.time() - self.last_request_time < 2:
            time.sleep(0.1)
        result = urllib2.urlopen(query_link).read()
        self.last_request_time = time.time()
        return result

    def get_aggregated_assignments(self):
        #filtered = self.assignments[self.assignments.Amount < 5]
        #filtered = filtered[self.assignments.UnitType == 'passengers']
        #grouped = filtered.groupby(['FromIcao', 'ToIcao'], as_index=False)
        grouped = self.assignments.groupby(['FromIcao', 'ToIcao'], as_index=False)
        aggregated = grouped.aggregate(np.sum)
        return aggregated.sort('Pay', ascending=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skey', help='Service key')
    parser.add_argument('--ukey', help='User key')
    parser.add_argument('--local', help='Use local dump of assignments instead of update', type=bool, default=True)
    args = parser.parse_args()
    if not (args.skey or args.ukey):
        raise Exception('You have to provide userkey or service key')
    fse = FSEconomy(False, args.ukey, args.skey)

    for col in fse.assignments.columns:
        if 'Unnamed' in col:
            del fse.assignments[col]

    # Searching best flight
    aggregated = fse.get_aggregated_assignments()[:10]

    def get_best_craft(icao):
        print 'Searching for best aircraft from {}'.format(icao)
        max_seats = 0
        best_aircraft = None
        for near_icao in fse.get_closest_airports(icao, 50).icao:
            aircrafts = fse.get_aircrafts_by_icao(near_icao)
            if not len(aircrafts):
                continue
            merged = pd.DataFrame.merge(aircrafts, fse.aircrafts, left_on='MakeModel', right_on='Model', how='inner')
            aircraft = merged.ix[merged.Seats.idxmax()]
            # TODO: filter ignored aircrafts
            if not aircraft.RentalWet + aircraft.RentalDry or aircraft.MakeModel in const.IGNORED_AIRCRAFTS:
                continue
            if aircraft.Seats > max_seats:
                best_aircraft = aircraft
                max_seats = aircraft.Seats
        return best_aircraft

    best_aircrafts = aggregated.FromIcao.map(lambda icao: get_best_craft(icao)).dropna()
    aggregated['MakeModel'] = best_aircrafts.map(lambda x: x.MakeModel)
    aggregated = aggregated.dropna()
    aggregated['CraftLocation'] = best_aircrafts.map(lambda x: x.Location)
    aggregated['CraftSeats'] = best_aircrafts.map(lambda x: x.Seats)
    aggregated['CraftCruise'] = best_aircrafts.map(lambda x: x.Cruise)
    aggregated['RentalDry'] = best_aircrafts.map(lambda x: x.RentalDry)
    aggregated['RentalWet'] = best_aircrafts.map(lambda x: x.RentalWet)
    aggregated = aggregated[(aggregated.RentalDry > 0) | (aggregated.RentalWet > 0)]

    craft_distance_func = lambda x, fse=fse: fse.get_distance(x['FromIcao'], x['CraftLocation'])
    aggregated['CraftDistance'] = aggregated.apply(craft_distance_func, axis=1)

    distance_func = lambda x, fse=fse: fse.get_distance(x['FromIcao'], x['ToIcao'])
    aggregated['Distance'] = aggregated.apply(distance_func, axis=1)

    rent_func = lambda x: (x['Distance'] + x['CraftDistance']) * x['RentalDry'] / x['CraftCruise']
    aggregated['Rent'] = aggregated.apply(rent_func, axis=1)

    # TODO: do smth with dry
    def get_earnings(x):
        res = x['Pay'] / x['Amount'] * min(x['CraftSeats'], x['Amount']) # dirty earnings
        if x['PtAssignment'] > 6:
            res -= res * x['PtAssignment'] / 100                        # booking fee
        t = (x['Distance'] + x['CraftDistance']) / x['CraftCruise']               # flight time
        return round(res - t * x['RentalWet'], 2)
    aggregated['Earnings'] = aggregated.apply(get_earnings, axis=1)


    coef_func = lambda x: round(x['Earnings'] / ((x['Distance'] + x['CraftDistance']) / x['CraftCruise']), 2)
    aggregated['Ratio'] = aggregated.apply(coef_func, axis=1)
    print aggregated

if __name__ == "__main__":
    main()
