import json
import re
import readline
import rlcompleter
import math

class SimpleCompleter(object):
    """
    Constructor:
    :param list options - A list of valid options
    """

    def __init__(self, options):
        self.options = sorted(options)

    def complete(self, text, state):
        response = None
        if state == 0:
            # This is the first time for this text, so build a match list.
            if text:
                self.matches = [s for s in self.options if s and s.lower().startswith(text.lower())]
            else:
                self.matches = self.options[:]

        # Return the state'th item from the match list,
        # if we have that many.
        try:
            response = self.matches[state]
        except:
            response = None
        return response

class OptionCompleter(object):
    """
    Constructor:
    :param Collection options
        Pack multiple level of options in dict
    """

    def __init__(self, options):
        self.options = options
        self.current_candidates = []

    def _unpack(self, source, *args):
        if source is None:
            source = self.options
        if isinstance(source, dict):
            if not len(args):
                return source.keys()
            elif args[0] in source:
                return self._unpack(source[args[0]], *args[1:])
            else:
                return []
        elif isinstance(source, list):
            return source
        else:
            return [source]

    def complete(self, text, state):
        response = None
        if state == 0:
            # This is the first time for this text, so build a match list.

            orgline = readline.get_line_buffer()
            begin = readline.get_begidx()
            end = readline.get_endidx()
            being_completed = orgline[begin:end]
            unpack_words = orgline[:begin].split()

            try:
                candidates = self._unpack(self.options, *unpack_words)

                if being_completed:
                    # match options with portion of input
                    # being completed
                    self.current_candidates = [ w for w in candidates
                                                if w.lower().startswith(being_completed.lower()) ]
                else:
                    # matching empty string so use all candidates
                    self.current_candidates = candidates

            except (KeyError, IndexError), err:
                self.current_candidates = []

        try:
            response = self.current_candidates[state]
        except IndexError:
            response = None
        return response

def get_help_text(toPrint, delim='\t', fstr=None, show_index=True):
    if not fstr:
        length = min([len(t) for t in toPrint])
        if length == 0:
            return ''
        fstr = ['{:<%d}' % (max([len(str(t[i])) for t in toPrint])) for i in range(length)]
        fstr = delim.join(fstr)
    return '\n'.join([ (show_index and '{:>2}'.format(i+1) or ' ') + '  ' + fstr.format(*t) for i, t in enumerate(toPrint)])

def has_enough_args(args, expected=0, warn=True):
    if expected <= len(args):
        return True
    if warn:
        print 'Error: Expecting %d+ arguments, obtained %d' % (expected, len(args))
    return False

class BasicItem(object):
    def __init__(self, name, args, htext=None, shortcuts=None):
        self._name = name
        self._help = htext or 'Executes {}'.format(name)
        self._args = args
        if shortcuts is not None:
            try:
                self._shortcut = list(shortcuts)
            except:
                self._shortcut = [shortcuts]
        else:
            self._shortcut = []

    def name(self):
        return self._name

    def callname(self):
        return self._name

    def shortcuts(self):
        return self._shortcut

    def help_text(self, fstr):
        return fstr.format(self._name, self._args, self._help)

    def reg_shortcut(self, *shortcuts):
        self._shortcut.extend(shortcuts)

    def lengths(self):
        return [len(getattr(self, s)) for s in ['_name', '_args', '_help']]

    def valid(self, num_of_args):
        return True

    def invalid_msg(self, num_of_args):
        return "ERROR: SHOULDN'T REACH HERE"

class AbstractMenu(object):
    """ The abstact class for menu"""
    def __init__(self):
        self._help = BasicItem('help', '', htext='Show this help message')
        self.arguments = []
        self.firstArgs = {}
        #self.help_text = None
        self.prompt = 'Abstract$ '

    def prelude(self):
        raise NotImplementedError()

    def main_loop(self):
        self.firstArgs = {s: i for i in self.arguments for s in [i.name()] + i.shortcuts()}
        func = None
        self._main_before()
        while not func:
            self.prelude()
            print ''
            try:
                order = raw_input(self.prompt).strip()
            except:
                print 'q'
                order = 'q'
            print ''
            order = order.split()
            try:
                o = order[0]
            except:
                continue
            self._main_before_run()
            if o == 'help':
                self.help(*order[1:])
                continue
            if o not in self.firstArgs:
                print 'Error: "%s" is not a valid option!' % o
                continue
            if not self.firstArgs[o].valid(len(order) - 1):
                print self.firstArgs[o].invalid_msg(len(order) - 1)
                continue
            func = self.run(self.firstArgs[o], *order[1:])
            self._main_after_run()
        self._main_after()
        print func

    def _main_before(self):
        pass

    def _main_after(self):
        pass

    def _main_before_run(self):
        pass

    def _main_after_run(self):
        pass

    def help(self, *args):
        cst = self._help.lengths()
        for arg in self.arguments:
            cst = [max(e, arg.lengths()[i]) for i, e in enumerate(cst)]
        # fstr = ['{:>%d}' % int(math.log10(len(self.arguments))+2)] + ['{:<%d}' % c for c in cst]
        fstr = '\t'.join(['{:<%d}' % c for c in cst])
        for arg in self.arguments + [self._help]:
            print arg.help_text(fstr)

    def run(self, item, *args):
        return getattr(self.__class__, item.callname())(self, *args)


class PromptItem(BasicItem):

    @staticmethod
    def defaultList(x=None):
        return []

    def __init__(self, name, args, htext=None, shortcuts=None, listf=None, realName=None):
        super(PromptItem, self).__init__(name, args, htext, shortcuts)
        self._listf = listf or PromptItem.defaultList
        self._realName = realName or self._name

    def name(self):
        return self._realName

    def promptList(self, arg):
        return self._listf(arg)


class PromptTestItem(PromptItem):
    def __init__(self, name, args, num_valid=0, htext=None, shortcuts=None, listf=None, realName=None):
        super(PromptTestItem, self).__init__(name, args, htext, shortcuts, listf, realName)
        self._num = num_valid

    def valid(self, num_of_args):
        return num_of_args >= self._num

    def invalid_msg(self, num_of_args):
        return 'Error: Expecting %d+ arguments, obtained %d' % (self._num, num_of_args)

class AbstractCompleteMenu(AbstractMenu):
    def __init__(self):
        super(AbstractCompleteMenu, self).__init__()

    def _genCompleter(self):
        raise NotImplementedError()

    def prelude(self):
        readline.set_completer(self._genCompleter().complete)
        self._prelude_1()

    def _prelude_1(self):
        raise NotImplementedError()

def baseline_init():
    if not readline.__doc__ or 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")

