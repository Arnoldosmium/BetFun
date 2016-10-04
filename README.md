# BetFun
## A python command line program to bet soccer events

**Key Features**:
- Automatically scrape bets and result information to execute bets
- User customizable soccer league selection
- Auto complete commandline with readline 
- Some (well not much...) Vim friendly shortcuts (lol)
- Some (commonly mistyped) bash shortcuts

Potentially Vunerability / Bug:
- Since Element Tree is used for parsing xml. All the vunerability is inherited.
- Some potentially failure from the data source.
- (Mainly) The coder's stupidity (lol)

**Data source**:
- odds: [_pinnaclesports_](http://xml.pinnaclesports.com/ "Pinnacle")
- results: [_football-data.org_](http://api.football-data.org/index "Football-data")

_Why I did this?_
- I'm a soccer fan. A Deportivo de La Coruña fan.
- I have no money to bet / Bet like someone with $10M (lol)
- Some future machine learning stuff.
