import pandas as pd
import pickle
import time
import urllib2
import numpy as np
from math import radians
from pulp import LpMaximize, LpProblem, LpVariable
from StringIO import StringIO

import common
import const


class TooManyConnectionsException(Exception):
    pass


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

    def get_aggregated_assignments(self, cargo=False):
        if cargo:
            self.assignments = self.assignments[self.assignments.UnitType == 'kg']
        else:
            self.assignments = self.assignments[self.assignments.UnitType == 'passengers']
        grouped = self.assignments.groupby(['FromIcao', 'ToIcao'], as_index=False)
        aggregated = grouped.aggregate(np.sum)
        return aggregated.sort('Pay', ascending=False)

    def get_aircrafts_by_icao(self, icao):
        data = common.retry(self.get_query, const.LINK + 'query=icao&search=aircraft&icao={}'.format(icao))
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

    def get_best_assignments(self, row):
        df = self.assignments[(self.assignments.FromIcao == row['FromIcao']) &
                              (self.assignments.ToIcao == row['ToIcao']) & (self.assignments.Amount <= row['Seats'])]
        if not len(df):
            return None
        prob = LpProblem("Knapsack problem", LpMaximize)
        w_list = df.Amount.tolist()
        p_list = df.Pay.tolist()
        x_list = [LpVariable('x{}'.format(i), 0, 1, 'Integer') for i in range(1, 1 + len(w_list))]
        prob += sum([x*p for x, p in zip(x_list, p_list)]), 'obj'
        prob += sum([x*w for x, w in zip(x_list, w_list)]) <= row['Seats'], 'c1'
        prob.solve()
        return df.iloc[[i for i in range(len(x_list)) if x_list[i].varValue]]

    def get_best_craft(self, icao, radius):
        print 'Searching for the best aircraft from {}'.format(icao)
        max_seats = 0
        best_aircraft = None
        for near_icao in self.get_closest_airports(icao, radius).icao:
            print '--Searching for the best aircraft from {}'.format(near_icao)
            aircrafts = self.get_aircrafts_by_icao(near_icao)
            if not len(aircrafts):
                continue
            merged = pd.DataFrame.merge(aircrafts, self.aircrafts, left_on='MakeModel', right_on='Model', how='inner')
            merged = merged[(~merged.MakeModel.isin(const.IGNORED_AIRCRAFTS)) & (merged.RentalWet + merged.RentalDry > 0)]
            if not len(merged):
                continue
            aircraft = merged.ix[merged.Seats.idxmax()]
            if aircraft.Seats > max_seats:
                best_aircraft = aircraft
                max_seats = aircraft.Seats
        return best_aircraft

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

    def get_jobs_from(self, icaos):
        return common.retry(self.get_query, const.LINK + 'query=icao&search=jobsfrom&icaos={}'.format('-'.join(icaos)))

    def get_distance(self, from_icao, to_icao):
        lat1, lon1 = [radians(x) for x in self.airports[self.airports.icao == from_icao][['lat', 'lon']].iloc[0]]
        lat2, lon2 = [radians(x) for x in self.airports[self.airports.icao == to_icao][['lat', 'lon']].iloc[0]]
        return common.get_distance(lat1, lon1, lat2, lon2)

    def get_logs(self, from_id):
        key = self.user_key or self.service_key
        data = common.retry(self.get_query, const.LINK +
                            'query=flightlogs&search=id&readaccesskey={}&fromid={}'.format(key, from_id))
        logs = pd.DataFrame.from_csv(StringIO(data))
        logs = logs[(logs.MakeModel != 'Airbus A321') & (logs.MakeModel != 'Boeing 737-800') & (logs.Type == 'flight')]
        logs['Distance'] = logs.apply(lambda x, self=self: self.get_distance(x['From'], x['To']), axis=1)
        logs = pd.merge(logs, self.aircrafts, left_on='MakeModel', right_on='Model')
        logs['FlightTimeH'] = logs.apply(lambda x: int(x['FlightTime'].split(':')[0]), axis=1)
        logs['FlightTimeM'] = logs.apply(lambda x: int(x['FlightTime'].split(':')[1]), axis=1)
        logs = logs[(logs.FlightTimeH > 0) | (logs.FlightTimeM > 0)]
        logs = logs[logs.Distance > 0]
        logs['AvSpeed'] = logs.apply(lambda x: 60 * x['Distance'] / (60 * x['FlightTimeH'] + x['FlightTimeM']), axis=1)
        import pdb; pdb.set_trace()

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
            raise TooManyConnectionsException(result)
        return result

