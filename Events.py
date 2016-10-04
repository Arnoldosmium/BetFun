from time import *
import readline
import math
from collections import Counter
from datetime import datetime
import re

_DATE_FORMAT = '%Y-%m-%d-%H:%M'

def _podd(odd, length):
    return '{:.{pres}f}'.format(odd, pres=max(length - int(math.log10(odd)) - 1, 0))

def _shorten(name):
    name = re.sub('[^A-Za-z]|\(.+?\)', '', name)
    return re.sub('a|e|i|o|u', '', name)

def _abbr(name):
    return re.sub('[^A-Z]', '', name)

def _unify(counter):
    keys, iterable = zip(*counter.items())
    s = math.sqrt(sum([i ** 2 for i in iterable]))
    return Counter(dict(zip(keys, [float(i) / s for i in iterable])))

def _cosine(c1, c2):
    c1 = _unify(c1)
    c2 = _unify(c2)
    common = [k for k in c1 if k in c2]
    return sum([c1[k] * c2[k] for k in common])

def toOdds(*mls):
    rtn = []
    for o in mls:
        try:
            assert not isinstance(o,str)
            rtn.extend(toOdds(*[e for e in o]))
        except:
            o = int(o)
            rtn.append(round((abs(o)+100.0)/((o >= 0) and 100 or -o), 3))
    return rtn

class AbstractBetType(object):
    def __init__(self, match_time, match_key, period, **kwargs):
        """
        Abstract bet type
        :param match_time: bet event time
        :param bteams: bet event teams - list/tuple<str>, size 2
        :param match_key: bet event key
        :param kwargs:
        """
        self.name = 'Abstract Bet'
        self.time = isinstance(match_time, str) and datetime.strptime(match_time, _DATE_FORMAT) or match_time
        # self.teams = bteams
        self._ekey = str(match_key)
        self.period = period
        self.bets = []
        if 'bets' in kwargs:
            for l in kwargs['bets']:
                self.doBet(*l)
        self.total_bet = sum([t[0] for t in self.bets])
        # self.odds = []

    def __str__(self):
        raise NotImplementedError

    def execute(self, results):
        raise NotImplementedError

    def doBet(self, bet, sub_event):
        self.bets.append((bet,sub_event))

    def ekey(self):
        return self._ekey

    def bkey(self):
        raise NotImplementedError

    def key(self):
        return str(hash(self._ekey) & 31) + self.bkey()

    def bet_details(self):
        return [(bet, '{1} @ {0}'.format(*self.odds_str(subev))) for bet, subev in self.bets]

    def odds_str(self, subev):
        raise NotImplementedError

    def toDict(self):
        return {'match_key': self._ekey,
                'match_time': self.time.strftime(_DATE_FORMAT),
                'period': self.period,
                'odds': self.odds,
                'bets': self.bets,
                'type': self.name}


class Moneyline(AbstractBetType):
    def __init__(self, odds, **kwargs):
        """
        Moneyline - regular W - D - L
        :param odds: array of bets in home - draw - visiting pattern
        :param kwargs: other arguments potentially used by abstract type

        sub events - 1 , 0 , -1
        """
        self.odds = odds
        super(Moneyline, self).__init__(**kwargs)
        self.name = 'Moneyline'


    @staticmethod
    def catagorization(h, a, *others):
        return (h - a) and (h - a) / abs(h - a) or 0

    def execute(self, results):
        """
        Execute the bet rule on result
        :param results: array of result in home - visiting pattern
        :return: Money getting back
        """
        tsubev = Moneyline.catagorization(*results)      # 1 - home won; 0 - draw; -1 - away won
        return sum([ (subev == tsubev) and self.odds[(1-tsubev)] * bet or 0
                     for bet, subev in self.bets ])  # 1 - tsubev = 0, 1, 2 respectively

    def odds_str(self, subev):
        return zip(self.odds, ['Win', 'Draw', 'Lose'])[1-subev]

    def bkey(self):
        return 'M' + ''.join(['{:.2f}'.format(o) for o in self.odds])

    def __str__(self):
        return '  '.join([_podd(o, 4) for o in self.odds])

class Spread(AbstractBetType):
    def __init__(self, odds, **kwargs):
        """
        Spread play - +1, +1.25, ...
        :param odds: list<tuple<adjust, odds>>
        :param kwargs:
        sub event - 1 Home, -1 Away
        """
        self.odds = odds
        self._bets = []
        super(Spread, self).__init__(**kwargs)
        self.name = 'Spread'


    @staticmethod
    def catagorization(adjust, h, a, *others):
        return Moneyline.catagorization(h+adjust, a)

    def execute(self, results):
        return sum([ ((Spread.catagorization(adj, *results) == subev) and bet * self.odds[int(0.5-subev)][1] or 0 ) +
                     ((Spread.catagorization(adj, *results) == 0) and bet or 0)
                       for bet, adj, subev in self._bets])

    def bkey(self):
        return 'S'+ ''.join(['{:d}{:.2f}'.format(int(o[0] * 4), o[1]) for o in self.odds])

    def odds_str(self, subev):
        odd, opt = zip(self.odds, ['Home', 'Away'])[int(0.5-subev)]
        return (odd[1], '{} ({:+}) Win'.format(opt, odd[0]))

    def __str__(self):
        return '  '.join(['{:<7}{}'.format('({:+})'.format(o[0]), _podd(o[1],4)) for o in self.odds])

    def doBet(self, bet, sub_event):
        """
        bet tuple: $bet, adjust, sub_event
        """
        super(Spread, self).doBet(bet, sub_event)
        adj = self.odds[int(0.5-sub_event)][0] * sub_event
        if int(adj*4) & 1:
            self._bets.append((bet/2.0, adj+0.25, sub_event))
            self._bets.append((bet/2.0, adj-0.25, sub_event))
        else:
            self._bets.append((bet, adj, sub_event))

class TotalGoals(AbstractBetType):

    def __init__(self, odds, **kwargs):
        """
        Total goals @ full time
        :param goalnum: sperating goal number
        :param odds: list<odd over, odd under>
            -> odds(goal, over, under)
        :param kwargs:
        sub events - +1 over; -1 under
        """
        self.odds = odds
        if 'goalnum' in kwargs:
            self.goalnum = kwargs['goalnum']
            self._odds = odds
            self.odds = [self.goalnum, self._odds]
        else:
            self.goalnum = odds[0]
            self._odds = odds[1]
        self._bets = []
        super(TotalGoals, self).__init__(**kwargs)
        self.name = 'TotalGoals'


    def doBet(self, bet, sub_event):
        super(TotalGoals, self).doBet(bet, sub_event)
        if int(self.goalnum * 4) & 1:
            self._bets.append((bet / 2.0, self.goalnum + 0.25, sub_event))
            self._bets.append((bet / 2.0, self.goalnum - 0.25, sub_event))
        else:
            self._bets.append((bet, self.goalnum, sub_event))

    def odds_str(self, subev):
        return zip(self.odds[1], ['{} {}'.format(s, self.odds[0]) for s in ['Over', 'Under']])[int(0.5 - subev)]

    def bkey(self):
        return 'T' + ''.join(['{:d}{:.2f}'.format(int(self.goalnum * 4), o) for o in self._odds])

    def execute(self, results):
        rgoal = sum(results)
        return sum([(((rgoal - goal) / subev > 0) and bet * self._odds[int(0.5 - subev)] or 0) +
                    ((rgoal == goal) and bet or 0)
                    for bet, goal, subev in self._bets])

    def __str__(self):
        return '{1} (+{0:^6}-) {2}'.format(self.goalnum, *[_podd(o, 4) for o in self._odds])

class BetEvent:

    def __init__(self, teams_rel, ddl, opens):
        """
        A soccer event for bet
        :param teams_rel: tuple team_name
        :param ddl: start of match
        :param opens: a xml node with details of betting lines
        """
        self.teams = tuple(teams_rel)
        self.deadline = ddl
        self._bkwargs = {
            'match_time': self.deadline,
            'bteams': self.teams,
            'match_key': self.key(),
            'period': opens.find('period_description').text
        }
        if opens.find('moneyline') is not None:
            self.moneyline = Moneyline(odds=toOdds(*[opens.find('moneyline').find(t).text
                             for t in ['moneyline_home', 'moneyline_draw', 'moneyline_visiting']]), **self._bkwargs)
        if opens.find('spread') is not None:
            self.spread = Spread(odds=[
                (float(opens.find('spread').find('spread_%s' % t).text),
                 toOdds(opens.find('spread').find('spread_adjust_%s' % t).text)[0]) for t in 'home', 'visiting'], **self._bkwargs)
        if opens.find('total') is not None:
            self.total = TotalGoals(goalnum=float(opens.find('total').find('total_points').text),
                                    odds=toOdds([opens.find('total').find(t).text
                                                 for t in ['over_adjust', 'under_adjust']]), **self._bkwargs)

    def name(self):
        return ' - '.join(self.teams)

    def __str__(self):
        return '    '.join([str(getattr(self, t, ' '*l)) for t,l in zip(['moneyline','spread','total'], [19,26,22])])

    def __len__(self):
        return len(self.name())

    def __cmp__(self, other):
        if not isinstance(other, BetEvent):
            return 1
        time = (self.deadline - other.deadline).total_seconds()
        if time:
            return time
        a = ''.join(self.teams)
        b = ''.join(other.teams)
        return (a < b) and -1 or ((a > b) and 1 or 0)

    @staticmethod
    def _teamkey(teams):
        return ''.join([str(hash(tm) & 65535) + _abbr(tm) for tm in teams])

    @staticmethod
    def _timekey(st_time):
        # return '{0.tm_year}{0.tm_mon:0>2}{0.tm_mday:0>2}{0.tm_hour:0>2}{0.tm_min:0>2}'.format(st_time)
        return st_time.strftime('%Y%m%d%H%M')

    def key(self):
        return BetEvent._timekey(self.deadline) + BetEvent._teamkey(self.teams)

    def toDict(self):
        return {'teams': self.teams,
                'match_time': self.deadline.strftime(_DATE_FORMAT),
                'period': self._bkwargs['period']}