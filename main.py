import argparse
import pandas as pd
import pickle
import time
import urllib2
import numpy as np
from math import radians
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
        aircrafts.RentalDry = aircrafts.RentalDry.astype(float)
        aircrafts.RentalWet = aircrafts.RentalWet.astype(float)
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
        lat1, lon1 = [radians(x) for x in self.airports[self.airports.icao == from_icao][['lat', 'lon']].iloc[0]]
        lat2, lon2 = [radians(x) for x in self.airports[self.airports.icao == to_icao][['lat', 'lon']].iloc[0]]
        return common.get_distance(lat1, lon1, lat2, lon2)

    def get_query(self, query_link):
        if self.user_key:
            query_link += '&userkey={}'.format(self.user_key)
        elif self.service_key:
            query_link += '&servicekey={}'.format(self.service_key)
        while time.time() - self.last_request_time < 2.5:
            time.sleep(1)
        result = urllib2.urlopen(query_link).read()
        self.last_request_time = time.time()
        if 'request was under the minimum delay' in result:
            import pdb; pdb.set_trace()
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
    parser.add_argument('--local', help='Use local dump of assignments instead of update', action='store_true')
    parser.add_argument('--limit', help='Limit for search', type=int, default=10)
    parser.add_argument('--radius', help='Radius for aircraft search (nm)', type=int, default=50)
    parser.add_argument('--debug', help='Use this key to enable debug breakpoints', action='store_true')
    args = parser.parse_args()
    if not (args.skey or args.ukey):
        raise Exception('You have to provide userkey or service key')

    fse = FSEconomy(args.local, args.ukey, args.skey)

    # TODO: we have unnamed columns after data fetching
    for col in fse.assignments.columns:
        if 'Unnamed' in col:
            del fse.assignments[col]

    # Searching best flight
    # TODO: make while loop here, because some groups of assignments could be impossible to do
    aggregated = fse.get_aggregated_assignments()[:args.limit]

    def get_best_craft(icao):
        print 'Searching for the best aircraft from {}'.format(icao)
        max_seats = 0
        best_aircraft = None
        for near_icao in fse.get_closest_airports(icao, args.radius).icao:
            print '--Searching for the best aircraft from {}'.format(near_icao)
            aircrafts = fse.get_aircrafts_by_icao(near_icao)
            if not len(aircrafts):
                continue
            merged = pd.DataFrame.merge(aircrafts, fse.aircrafts, left_on='MakeModel', right_on='Model', how='inner')
            aircraft = merged.ix[merged.Seats.idxmax()]
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
    # TODO: filter it when we searching for aircraft
    aggregated = aggregated[(aggregated.RentalDry > 0) | (aggregated.RentalWet > 0)]

    craft_distance_func = lambda x, fse=fse: fse.get_distance(x['FromIcao'], x['CraftLocation'])
    aggregated['CraftDistance'] = aggregated.apply(craft_distance_func, axis=1)

    distance_func = lambda x, fse=fse: fse.get_distance(x['FromIcao'], x['ToIcao'])
    aggregated['Distance'] = aggregated.apply(distance_func, axis=1)
    aggregated['DryRent'] = aggregated.apply(common.get_rent, args=('RentalDry',), axis=1)
    aggregated['WetRent'] = aggregated.apply(common.get_rent, args=('RentalWet',), axis=1)
    aggregated['DryEarnings'] = aggregated.apply(common.get_earnings, args=('DryRent', fse.assignments), axis=1)
    aggregated['WetEarnings'] = aggregated.apply(common.get_earnings, args=('WetRent', fse.assignments), axis=1)
    aggregated['DryRatio'] = aggregated.apply(common.get_ratio, args=('DryEarnings',), axis=1)
    aggregated['WetRatio'] = aggregated.apply(common.get_ratio, args=('WetEarnings',), axis=1)
    print aggregated.sort('Ratio', ascending=False)
    if args.debug:
        import pdb; pdb.set_trace()

if __name__ == "__main__":
    main()
