# FSEconomy
This is a small simple command-line tool for searching optimal assignments in FSEconomy addon (http://www.fseconomy.net/)

### Requirements
First of all you need to have installed Python 2.7.
List of required modules:
 - pandas
 - numpy
 - pulp

Numpy on Windows requires: [Microsoft Visual C++ Compiler for Python 2.7](https://www.microsoft.com/en-us/download/details.aspx?id=44266)
 
### Usage
Simple search:
```
python main.py --skey={your service key here}
```
or
```
python main.py --ukey={your user key here}
```
First of all this tool will download info about all assignments from FSEconomy server. 
It's time consuming operation, so next time you can use *--local* parameter to use a local dump:
```
python main.py --ukey={your user key here} --local
```
Then FSEconomy tool will try to find an optimal route to maximize your earnings.

To set limit of airports use *--limit* (default value is 10):
```
python main.py --ukey={your user key here} --limit=5 --local
```

To set aircraft search radius use *--radius* (default value is 50nm)
```
python main.py --ukey={your user key here} --limit=5 --radius=100 --local
```

Output example:
```
      FromIcao ToIcao  Amount    Pay PtAssignment All-In  \
47479     PHTO   PHBK     184  70595        False  False
52915     SCTE   SAVC     125  56874        False  False

                           MakeModel CraftLocation  CraftSeats  CraftCruise  \
47479          Bristol Britannia 300          HI28         105          330
52915          Bristol Britannia 300          SCAC         105          330

       RentalDry  RentalWet  CraftDistance  Distance  DryRent   WetRent  \
47479       2500      10000           38.6     299.9  2564.39  10257.58
52915       7044      11454           42.9     358.7  8572.33  13939.17

       DryEarnings  WetEarnings  DryRatio  WetRatio
47479     29539.61     21846.42  28797.85  21297.84
52915     22617.67     17250.83  18585.24  14175.23
```
It means that best option now is:
 - to rent **Bristol Britannia 300** in **HI28** 
 - fly **38.6** miles to **PHTO**
 - add assignments to **PHBK** (I have to add some info about what specific assignments are optimal)
 - fly!
 
### Issues
See issues in my GitHub repository. If you expirienced some that I haven't notice, don't be shy to notify me.
