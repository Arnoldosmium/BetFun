from Menu import AbstractCompleteMenu, SimpleCompleter, OptionCompleter, PromptTestItem, baseline_init
from Events import *
import readline
import json
from datetime import datetime
from time import gmtime, localtime, strftime
import urllib2
import unirest
import xml.etree.ElementTree as ET
import re
from collections import OrderedDict, Counter
import pytz

_DATE_FORMAT = '%Y-%m-%d-%H:%M'
_HourDiff = datetime.strptime(strftime(_DATE_FORMAT, gmtime()), _DATE_FORMAT) - datetime.strptime(strftime(_DATE_FORMAT, localtime()), _DATE_FORMAT)
_sdict = {c.__name__: c for c in [Moneyline, Spread, TotalGoals]}

def _gmtNow():
    return datetime.strptime(strftime(_DATE_FORMAT, gmtime()), _DATE_FORMAT)

def _pdtime(td):
    m = td.seconds / 60
    if not m:
        return '<1 min'
    h = m / 60
    return ' '.join(['{1:>2} {2:>2}{0}'.format((t[0] > 1) and 's' or ' ',*t)
                     for t in zip([td.days, h, m%60], ['day', 'hour', 'min']) if t[0]])

def _toUniCounter(name):
    name = re.sub('\(.+?\)|(cf)|(fc)|[^a-z]', '', name.lower())
    keys, counts = zip(*Counter(re.sub('a|e|i|o|u', '', str(name))).items())
    s = math.sqrt(sum([i**2 for i in counts]))
    return Counter(dict(zip(keys, [c/s for c in counts])))

def _cosine(c1, c2):
    return sum([c1[k] * c2[k] for k in c1 if k in c2])

class TickTock(object):

    def __init__(self):
        self.tick = datetime.now()

    def tock(self):
        return datetime.now() - self.tick

    def ptime(self, fstr='{:.2f} s', gen=lambda td: tuple([td.total_seconds()])):
        print fstr.format(*gen(self.tock()))


class MainMenu(AbstractCompleteMenu):

    def __init__(self):
        super(MainMenu, self).__init__()
        self.prompt = 'Betfun> '
        self.arguments = [
            PromptTestItem('acquireExtra', 'Money', num_valid=1, htext='Add new money to balance', shortcuts=[]),
            PromptTestItem('printLeagues', '', htext='Print current available leagues', shortcuts=['p', 'ls', 'list']),
            PromptTestItem('printMatches', '', htext='Print current available matches', shortcuts=['m', 'lm', 'match']),
            PromptTestItem('printBetHistory', '', htext='Print history', shortcuts=[':h', ':hist', 'history']),
            PromptTestItem('printPendingBets', '', htext='Print pending bets', shortcuts=['lb']),
            PromptTestItem('chooseLeague', 'league_name [print_flag]', num_valid=1, htext='Choose the league to work on',
                           shortcuts=['cd', 'cl'], listf=lambda x: ['_'.join(k.split()) for k in x._events.keys()]),
            PromptTestItem('showEvents', '[league_name]', htext='List current betable event in a league',
                           shortcuts=['show', 'll'], listf=lambda x: ['_'.join(k.split()) for k in x._events.keys()]),
            PromptTestItem('betOn', 'league_name match_num selection bets', num_valid=3, htext='Bet on specific match',
                           shortcuts=['bet', ':b'], listf=lambda x:['_'.join(k.split()) for k in x._events.keys()]),
            PromptTestItem('applyResult', 'match_num home-visiting', num_valid=2, htext='Apply result on specific match',
                           shortcuts=['apply'], listf=lambda x:[]),
            PromptTestItem('quit', '', htext='Exit bet fun', shortcuts=['q', ':q', 'exit'])
        ]
        ###
        # None Menu-critical
        ###
        try:
            self.record = json.load(open('rec.bin', 'r'))
        except:
            self.record = {'balance': 10000, 'match': {}, 'subevent': {}}
        self.matches = self.record['match']
        self.subevents = self.record['subevent']
        try:
            self.logs = json.load(open('log.json', 'r'))
        except:
            self.logs = {'bet_logs': [], 'knowledge': {'unmatch':[]}}
        self.knowledge = self.logs['knowledge']
        try:
            self.conf = json.load(open('conf.json','r'))
        except:
            self.conf = {"pref": ["FIFA", "Segunda", "Eng. F", "Eng. P", "USA"], "repat": ["UEFA C[A-Za-z]+$", "Serie A$", "La Liga$", "Bundesliga$"]}
        self.repat = [re.compile(r) for r in self.conf['repat']]
        self._events = {}
        self._pull_bets()
        self._pull_results()
        self._currlg = None
        self._doprint = False
        # self.results = {}

    def _prelude_1(self):
        self._execute_results()
        print
        print '='*30
        print 'Current Balance: ', self.record['balance']
        print '='*30
        if self._currlg is not None:
            print 'Current Focus League selection:', self._currlg
            if self._doprint:
                print '-'*30
                self.showEvents()
            print '='*30

    def _genCompleter(self):
        return OptionCompleter({i.name(): i._listf(self) for i in self.arguments})

    def _main_after_run(self):
        json.dump(self.record, open('rec.bin', 'w'))

    def _main_after(self):
        json.dump(self.conf, open('conf.json', 'w'))

    def _keep(self, key):
        for p in self.conf['pref']:
            if key.startswith(p):
                return True
        for r in self.repat:
            if r.match(key):
                return True
        return False

    def _pull_bets(self):
        tick = TickTock()
        print "Connecting the Server for Odds...",
        req = urllib2.Request('http://xml.pinnaclesports.com/')
        fin = urllib2.urlopen(req)
        tick.ptime()
        tick = TickTock()
        print "Parsing Bet data...",
        catag = {}
        for e in ET.parse(fin).getroot().find('events'):
            if not e.find('sporttype').text.startswith('Soccer') or e.find('periods') is None or not len(e.find('periods')):
                continue
            league = e.find('league').text
            if league not in catag:
                catag[league] = []
            catag[league].append(e)
        tick.ptime()
        tick = TickTock()
        print "Filteration ...",
        for k,v in catag.items():
            if not self._keep(k):
                continue
            if k not in self._events:
                self._events[k] = {}
            for e in v:
                opens = [p for p in e.find('periods') if p.find('period_description').text.lower()[0] == 'm']
                if not len(opens):
                    continue
                teams = sorted({p.find('visiting_home_draw').text: p.find('participant_name').text
                        for p in list(e.find('participants'))[:2]}.items())
                # TODO: UPDATE so that refreshable
                evt = BetEvent(
                    teams_rel=[p[1] for p in teams],
                    ddl=datetime.strptime(e.find('event_datetimeGMT').text, '%Y-%m-%d %H:%M'),
                    opens=opens[0])
                # TODO: set up different way of checking result
                self._events[k][evt.key()] = evt
            self._events[k] = OrderedDict(sorted(self._events[k].items(), key=lambda t: t[1]))
        tick.ptime()

    def _pull_results(self):
        if not len(self.matches):
            return

        # TODO: PLAN B - blacklist on event
        tick = TickTock()
        print 'Preparing match details...',
        matches = {k:dict(m) for k,m in self.matches.items() if 'unmatch' not in m}
        for m in matches.values():
            m['match_time'] = datetime.strptime(m['match_time'], _DATE_FORMAT)
            m['match_date'] = m['match_time'].date()
            m['homeVector'] = _toUniCounter(m['teams'][0])
            m['awayVector'] = _toUniCounter(m['teams'][1])

        days = max(0, *[(_gmtNow().date() - m['match_date']).days for m in matches.values()])
        days = min(days + 1, 99)
        tick.ptime()
        print 'Parsing fixtures...'
        hdr = {'X-Auth-Token': None,'X-Response-Control': 'minified'}
        prev = unirest.get('http://api.football-data.org/v1/fixtures?timeFrame=p{}'.format(days), header=hdr).body
        nxt =  unirest.get('http://api.football-data.org/v1/fixtures?timeFrame=n1', header=hdr).body
        if 'fixtures' not in prev:
            print 'Request 1 Fails!'
            print prev['error']
            prev = []
        else:
            prev = prev['fixtures']
        if 'fixtures' not in nxt:
            print 'Request 2 Fails!'
            print nxt
        else:
            nxt = nxt['fixtures']
        fixtures = [f for f in prev + nxt if f['status'].lower() == 'finished']
        if not len(fixtures):
            print 'No fixture data found...'
            return

        # TODO: MATCHING FIXTURES
        fxdict = {}
        for f in fixtures:

            # 1st try - team id match + key match

            mtime = datetime.strptime(f['date'], '%Y-%m-%dT%H:%M:%SZ')
            f['homeid'] = home = f['_links']['homeTeam']['href'][f['_links']['homeTeam']['href'].rfind('/')+1:]
            f['awayid'] = away = f['_links']['awayTeam']['href'][f['_links']['awayTeam']['href'].rfind('/')+1:]
            if home in self.knowledge and away in self.knowledge:
                key = BetEvent._timekey(mtime) + BetEvent._teamkey([self.knowledge[home][1], self.knowledge[away][1]])
                if key in matches:
                    self.matches[key]['result'] = (f['result']['goalsHomeTeam'], f['result']['goalsAwayTeam'])
                    print '\tReceives {0[0]} {0[1]}-{1[1]} {1[0]}'.format(*zip(self.matches[key]['teams'], self.matches[key]['result']))
                    continue

            # 2nd try pep - catg by time

            f['homeVector'] = _toUniCounter(f['homeTeamName'])
            f['awayVector'] = _toUniCounter(f['awayTeamName'])
            if mtime not in fxdict:
                fxdict[mtime] = []
            fxdict[mtime].append(f)
        print 'Matching trail...'
        unknown_results = {k:m for k,m in matches.items() if 'result' not in self.matches[k]}
        care_times = {m['match_time'] for m in unknown_results.values()}
        fxdict = {k: v for k,v in fxdict.items() if k in care_times}
        for k,m in unknown_results.items():
            if m['match_time'] not in fxdict:
                continue
            best_match_s = sorted(fxdict[m['match_time']],
                                key=lambda x: _cosine(m['homeVector'], x['homeVector']) * _cosine(m['awayVector'], x['awayVector']),
                                  reverse=True)[:5]
            for best_match in best_match_s:
                print '\tMatching "{} - {}"'.format(*m['teams']),
                print 'with "%s - %s"' % (best_match['homeTeamName'], best_match['awayTeamName'])
                selection = raw_input('\t\tAccept / Reject / Unmatchable:\t').lower()[0]
                if selection in 'ay':
                    self.knowledge[best_match['homeid']] = (best_match['homeTeamName'], m['teams'][0])
                    self.knowledge[best_match['awayid']] = (best_match['awayTeamName'], m['teams'][1])
                    self.matches[k]['result'] = (best_match['result']['goalsHomeTeam'], best_match['result']['goalsAwayTeam'])
                    break
                elif selection == 'u':
                    ###
                    # PLAN A HERE
                    ###
                    # self.knowledge['unmatch'].extend(m['teams'])
                    #
                    # TODO: When save matches, set up unmatch flag to matches - plan B
                    self.matches[k]['unmatch'] = 'True'
                    break
        self._saveLog()

    def _saveLog(self):
        json.dump(self.logs, open('log.json', 'w'))

    def _execute_results(self):
        revealed = []
        for k,v in sorted(self.subevents.items(), lambda x, y: cmp(x[1]['match_time'], y[1]['match_time'])):
            if v['match_key'] not in self.matches or 'result' not in self.matches[v['match_key']]:
                continue
            self._execute_onMatch(v, self.matches[v['match_key']])
            revealed.append(k)
        self.record['subevent'] = self.subevents = {k: v for k,v in self.subevents.items() if k not in revealed}
        care_key = {s['match_key'] for s in self.subevents.values()}
        self.record['match'] = self.matches = {k: v for k,v in self.matches.items() if k in care_key}
        self._saveLog()

    def _execute_onMatch(self, sube, match):
        s_sube = _sdict[sube['type']](**sube)   # create a _Mline/Sprd/Total_ based on dict
        got = s_sube.execute(match['result'])
        self.logs['bet_logs'].append(
            {'match': '{1[0]} {1[1]} - {2[1]} {2[0]} ({0})'.format(sube['type'], *zip(match['teams'], match['result'])),
             'date': match['match_time'],
             'total_get': got,
             'total_spend': s_sube.total_bet,
             'bets': s_sube.bet_details()})
        self.record['balance'] += got

    def _getLeagueKey(self, league):
        if league.isdigit():
            try:
                league = sorted(self._events.keys())[abs(int(league) - 1)]
            except:
                print 'ERROR: index {} is out of bound'.format(league)
                return
        else:
            league = league.replace('_', ' ')
            if league not in self._events:
                print 'ERROR: "{}" cannot be found.'.format(league)
                return
        return league

    def chooseLeague(self, league, *args):
        if league == '..':
            self._currlg = None
            self._doprint = False
            print 'Un-select the league'
            return
        league = self._getLeagueKey(league)
        if league is not None:
            self._currlg = league
            self._doprint = not (len(args) and args[0].startswith('--no') )

    def printLeagues(self, *args):
        print 'Current Leagues: '
        for i, l in enumerate(sorted(self._events.keys())):
            print '{:2>d} {}'.format(i + 1, l)

    def showEvents(self, *args):
        if not len(args) and self._currlg is not None:
            league = self._currlg
        else:
            try:
                league = self._getLeagueKey(args[0])
            except:
                print 'ERROR: Need 1+ arguments when focus league is not selected.'
                return
        if league is None:
            return
        teaml = max([len(e) for e in self._events[league].values()])
        print ' ' * (teaml + 2), '    '.join(['{:^{l}}'.format(t, l=l)
                                              for t,l in zip(['Moneyline','Spread','Total'], [19,26,22])])
        for i, e in enumerate(self._events[league].values()):
            print u'{:>2} {:<{namelen}}'.format(i+1, e.name(), namelen=teaml), str(e), '   in', _pdtime(e.deadline - _gmtNow())

    @staticmethod
    def _parse_option(option):
        opt, sub = option.split(':')
        if not opt or not sub:
            print 'ERROR: Invalid option:', option
            return None, None
        opta = opt.lower()[0]
        suba = sub.lower()[0]
        if opta == 'm':
            if suba in 'abcwdl123':
                return 'moneyline', (1 - 'abcwdl123'.find(suba) % 3)
        elif opta == 's':
            if suba in 'abwl12':
                return 'spread', [1, -1]['abwl12'.find(suba) % 2]
        elif opta == 't':
            if suba in 'abou12':
                return 'total', [1, -1]['abou12'.find(suba) % 2]
        print 'ERROR: Invalid option:', option
        return None, None

    def betOn(self, *args):
        if len(args) == 4:
            self._betOn(self._getLeagueKey(args[0]), *args[1:])
        elif len(args) == 3 and self._currlg is not None:
            self._betOn(self._currlg, *args)
        else:
            print 'ERROR: Arguments are not in correct length.'

    def _betOn(self, league, mnum, option, bet):
        """
        :param league: league_name or league id
        :param mnum: match id
        :param option: Option:Subevent
        :param bet: number of bets
        :param args:
        :return:
        """
        if league is None:
            return
        if not mnum.isdigit() or int(mnum) <= 0:
            print 'ERROR: Match number %d does not exist' % mnum
            return
        try:
            bet = float(bet)
            assert 0 < bet <= self.record['balance']
        except:
            print 'ERROR: Invalid bet %s' % bet
            return
        try:
            event = self._events[league].values()[int(mnum) - 1]
        except:
            print 'ERROR: Match number %s does not exist' % mnum
            return

        opt, sub = MainMenu._parse_option(option)
        if opt is None or sub is None:
            return
        try:
            beton = getattr(event, opt)
        except:
            print 'ERROR: Sub option "%s" is not available currently' % opt
            return

        print 'Bet {} on event "{}" with option "{}": \n\t{}'.format(bet, event.name(), option, str(event))
        # beton.doBet(bet, sub)
        if event.key() not in self.matches:
            self.matches[event.key()] = event.toDict()
        if beton.key() not in self.subevents:
            self.subevents[beton.key()] = beton.toDict()
        betd = self.subevents[beton.key()]['bets'].append((bet, sub))
        self.record['balance'] -= bet

    def printMatches(self, *args):
        for i, (k, m) in enumerate(sorted(self.matches.items())):
            t = datetime.strptime(m['match_time'], _DATE_FORMAT) - _HourDiff
            print '{:>2d} {}  {} - {}'.format(i+1, t, *m['teams'])

    def printPendingBets(self, *args):
        for s in sorted(self.subevents.values(), key=lambda e: e['match_key']):
            print u'{1} - {2} ({0})'.format(s['type'], *self.matches[s['match_key']]['teams'])
            for itm in s['bets']:
                print '{:>8}bet {} on {}'.format(' ', *itm)

    def printBetHistory(self, *args):
        if len(args) and args[0].isdigit():
            last_entry = int(args[0])
        else:
            last_entry = 10
        first = max(len(self.logs['bet_logs']) - last_entry, 0)
        for i, s in enumerate(self.logs['bet_logs'][first:]):
            print '{:>3d} {} {:+} {}'.format(i+first+1, s['date'][:10], s['total_get'] - s['total_spend'], s['match'])
            for itm in s['bets']:
                print '{:>8}bet {} on {}'.format(' ', *itm)

    def acquireExtra(self, money, *args):
        try:
            money = float(money)
        except:
            print 'ERROR: "%s" is not convertible to numbers.'
            return
        self.logs['bet_logs'].append({'date': datetime.now().strftime(_DATE_FORMAT), 'bets': [],
                                      'total_get': money, 'total_spend': 0, 'match': 'Issue new money'})
        self.record['balance'] += money

    def applyResult(self, mnum, result, *args):
        try:
            event = self.matches.values()[int(mnum) - 1]
        except:
            print 'ERROR: Match number %d does not exist' % mnum
            return

        try:
            if '-' in result:
                rslt = [int(r) for r in result.split('-')]
            elif ':' in result:
                rslt = [int(r) for r in result.split(':')]
            else:
                raise ValueError()
            assert len(rslt) == 2
        except:
            print 'ERROR: Result "%s" is not understandable' % result
            return
        event['result'] = rslt

    def quit(self, *args):
        return 'Quit'

if __name__ == '__main__':
    baseline_init()
    MainMenu().main_loop()
