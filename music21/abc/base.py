#-------------------------------------------------------------------------------
# Name:         abc.base.py
# Purpose:      music21 classes for dealing with abc data
#
# Authors:      Christopher Ariza
#
# Copyright:    (c) 2010 The music21 Project
# License:      LGPL
#-------------------------------------------------------------------------------
'''
Objects and tools for processing ABC data. 

'''

import music21
import unittest
import re

try:
    import StringIO # python 2 
except:
    from io import StringIO # python3 (also in python 2.6+)


from music21 import common
from music21 import environment
_MOD = 'abc.base.py'
environLocal = environment.Environment(_MOD)

# for implementation
# see http://abcnotation.com/abc2mtex/abc.txt

# store symbol and m21 naming/class eq
ABC_BARS = [
           ('|]', 'thin-thick double bar line'),
           ('||', 'thin-thin double bar line'),
           ('[|', 'thick-thin double bar line'),
           ('[1', 'first repeat'),
           ('[2', 'second repeat'),
           (':|', 'left repeat'),
           ('|:', 'right repeat'),
           ('::', 'left-right repeat'),
            # for comparison, single chars must go last
           ('|', 'bar line'),
           ]

#-------------------------------------------------------------------------------
# note inclusion of w: for lyrics
reMetadataTag = re.compile('[A-Zw]:')

rePitchName = re.compile('[a-gA-Gz]')

reChordSymbol = re.compile('"[^"]*"') # non greedy

reChord = re.compile('[.*?]') # non greedy



#-------------------------------------------------------------------------------
class ABCTokenException(Exception):
    pass

class ABCHandlerException(Exception):
    pass


#-------------------------------------------------------------------------------
class ABCToken(object):
    '''
    ABC processing works with a multi-pass procedure. The first pass breaks the data stream into a list of ABCToken objects. ABCToken objects are specialized in subclasses. 

    The multi-pass procedure is conducted by an ABCHandler object. The ABCHandler.tokenize() method breaks the data stream into ABCToken objects. The ABCHandler.tokenProcess() method first calls the preParse() method on each token, then does contextual adjustments to all tokens, then calls parse() on all tokens.


    '''
    def __init__(self, src=''):
        self.src = src # store source character sequence

    def __repr__(self):
        return '<ABCToken %r>' % self.src

    def stripComment(self, strSrc):
        '''
        removes ABC-style comments from a string:
        
        >>> ao = ABCToken()
        >>> ao.stripComment('asdf')
        'asdf'
        >>> ao.stripComment('asdf%234')
        'asdf'
        >>> ao.stripComment('asdf  %     234')
        'asdf  '
        
        >>> ao.stripComment('[ceg]% this chord appears 50% more often than other chords do')
        '[ceg]'
        '''
        if '%' in strSrc:
            return strSrc.split('%')[0] #
        return strSrc
    
    def preParse(self):
        '''Called before context adjustments. 
        '''
        pass

    def parse(self): 
        '''Read self.src and load attributes. Customize in subclasses.
        Called after context adjustments
        '''
        pass


class ABCMetadata(ABCToken):

    # given a logical unit, create an object
    # may be a chord, notes, metadata, bars
    def __init__(self, src):
        ABCToken.__init__(self, src)
        self.tag = None
        self.data = None

    def __repr__(self):
        return '<ABCMetadata %r>' % self.src

    def preParse(self):
        '''Called before context adjustments: need to have access to data
        '''
        div = reMetadataTag.match(self.src).end()
        strSrc = self.stripComment(self.src) # remove any comments
        self.tag = strSrc[:div-1] # do not get colon, :
        self.data = strSrc[div:].strip() # remove leading/trailing

    def parse(self):
        pass

    def isDefaultNoteLength(self):
        if self.tag == 'L': 
            return True
        return False

    def isMeter(self):
        if self.tag == 'M': 
            return True
        return False

    def isTitle(self):
        if self.tag == 'T': 
            return True
        return False

    def isComposer(self):
        if self.tag == 'C': 
            return True
        return False

    def isVoice(self):
        if self.tag == 'V': 
            return True
        return False

    def isKey(self):
        if self.tag == 'K': 
            return True
        return False


    def getTimeSignature(self):
        '''If there is a time signature representation available, get a numerator and denominator

        >>> am = ABCMetadata('M:2/2')
        >>> am.preParse()
        >>> am.getTimeSignature()
        (2, 2, 'normal')

        >>> am = ABCMetadata('M:C|')
        >>> am.preParse()
        >>> am.getTimeSignature()
        (2, 2, 'cut')
        '''
        if not self.isMeter():
            raise ABCTokenException('no time signature associated with this meta-data')

        if self.data == 'C':
            n, d = 4, 4
            symbol = 'common' # m21 compat
        elif self.data == 'C|':
            n, d = 2, 2
            symbol = 'cut' # m21 compat
        else:
            n, d = self.data.split('/')
            n = int(n.strip())
            d = int(d.strip())
            symbol = 'normal' # m21 compat

        return n, d, symbol

    def getTimeSignatureObject(self):
        '''Return a music 21 time signature ojbect
        '''
        if not self.isMeter():
            raise ABCTokenException('no time signature associated with this meta-data')
        from music21 import meter
        n, d, symbol = self.getTimeSignature()
        return meter.TimeSignature('%s/%s' % (n,d))


    def getKeySignature(self):
        '''Extract key signature parameters, include indications for mode, and translate sharps count compatible with m21, returning the number of sharps and the mode.

        >>> am = ABCMetadata('K:Eb Lydian')
        >>> am.preParse()
        >>> am.getKeySignature()
        (-2, 'lydian')

        >>> am = ABCMetadata('K:APhry')
        >>> am.preParse()
        >>> am.getKeySignature()
        (-1, 'phrygian')

        >>> am = ABCMetadata('K:G Mixolydian')
        >>> am.preParse()
        >>> am.getKeySignature()
        (0, 'mixolydian')

        >>> am = ABCMetadata('K: Edor')
        >>> am.preParse()
        >>> am.getKeySignature()
        (2, 'dorian')

        >>> am = ABCMetadata('K: F')
        >>> am.preParse()
        >>> am.getKeySignature()
        (-1, None)

        >>> am = ABCMetadata('K:G')
        >>> am.preParse()
        >>> am.getKeySignature()
        (1, None)

        >>> am = ABCMetadata('K:Hp')
        >>> am.preParse()
        >>> am.getKeySignature()
        (2, None)

        '''
        # placing this import in method for now; key.py may import this module
        from music21 import key

        if not self.isKey():
            raise ABCTokenException('no key signature associated with this meta-data')

        # abc uses b for flat in key spec only
        keyNameMatch = ['c', 'g', 'd', 'a', 'e', 'b', 'f#', 'g#', 
                        'f', 'bb', 'eb', 'ab', 'db', 'gb', 'cb',
                        # HP or Hp are used for highland pipes
                        'hp']

        # first, get standard key indication
        for target in keyNameMatch:
            if target == self.data[:len(target)].lower():
                # keep case
                standardKeyStr = self.data[:len(target)]
                stringRemain = self.data[len(target):]
        # replace a flat symbol if found; only the second char
        if standardKeyStr == 'HP':
            standardKeyStr = 'C' # no sharp or flats
        elif standardKeyStr == 'Hp':
            standardKeyStr = 'D' # use F#, C#, Gn
        if len(standardKeyStr) > 1 and standardKeyStr[1] == 'b':
            standardKeyStr = standardKeyStr[0] + '-'

        mode = None
        if stringRemain != '':
            # only first three characters are parsed
            modeCandidate = stringRemain.lower()
            for match, modeStr in [
                                   ('dor', 'dorian'),
                                   ('phr', 'phrygian'),
                                   ('lyd', 'lydian'),
                                   ('mix', 'mixolydian'),
                                   ('min', 'minor'),
                                  ]:
                if match in modeCandidate:
                    mode = modeStr
    
        # not yet implemented: checking for additional chromatic alternations
        # e.g.: K:D =c would write the key signature as two sharps 
        # (key of D) but then mark every  c  as  natural
 
        return key.pitchToSharps(standardKeyStr, mode), mode

    def getDefaultQuarterLength(self):
        '''If there is a quarter length representation available, return it as a floating point value

        >>> am = ABCMetadata('L:1/2')
        >>> am.preParse()
        >>> am.getDefaultQuarterLength()
        2.0

        >>> am = ABCMetadata('L:1/8')
        >>> am.preParse()
        >>> am.getDefaultQuarterLength()
        0.5

        >>> am = ABCMetadata('M:C|')
        >>> am.preParse()
        >>> am.getDefaultQuarterLength()
        0.5

        >>> am = ABCMetadata('M:2/4')
        >>> am.preParse()
        >>> am.getDefaultQuarterLength()
        0.25

        >>> am = ABCMetadata('M:6/8')
        >>> am.preParse()
        >>> am.getDefaultQuarterLength()
        0.5

        '''
        if self.isDefaultNoteLength():
            # should be in L:1/4 form
            n, d = self.data.split('/')
            n = int(n.strip())
            d = int(d.strip())
            # 1/4 is 1, 1/8 is .5
            return (float(n) / d) * 4
            
        elif self.isMeter():
            # meter auto-set a default not length
            n, d, symbol = self.getTimeSignature()
            if float(n) / d < .75:
                return .25 # less than 0.75 the default is a sixteenth note
            else:
                return .5 # otherwiseit is an eighth note

        else:       
            raise ABCTokenException('no quarter length associated with this meta-data')



class ABCBar(ABCToken):

    # given a logical unit, create an object
    # may be a chord, notes, metadata, bars
    def __init__(self, src):
        ABCToken.__init__(self, src)
        self.barType = None

    def __repr__(self):
        return '<ABCBar %r>' % self.src


class ABCTuplet(ABCToken):
    '''ABcTuplet tokens always precede the notes they describe.

    
    In ABCHandler.tokenProcess(), rhythms are adjusted. 

    '''
    def __init__(self, src):
        ABCToken.__init__(self, src)

        #self.qlRemain = None # how many ql are left of this tuplets activity
        # how many notes are affected by this; this assumes equal duration
        self.noteCount = None         

        # actual is tuplet represented value; 3 in 3:2
        self.numberNotesActual = None
        #self.durationActual = None

        # normal is underlying duration representation; 2 in 3:2
        self.numberNotesNormal = None
        #self.durationNormal = None

        # store an m21 tuplet object
        self.tupletObj = None

    def __repr__(self):
        return '<ABCTuplet %r>' % self.src

    def updateRatio(self, keySignatureObj=None):
        '''Cannot be called until local meter context is established

        >>> at = ABCTuplet('(3')
        >>> at.updateRatio()
        >>> at.numberNotesActual, at.numberNotesNormal
        (3, 2)

        >>> at = ABCTuplet('(5')
        >>> at.updateRatio()
        >>> at.numberNotesActual, at.numberNotesNormal
        (5, 2)

        >>> from music21 import meter
        >>> at = ABCTuplet('(5')
        >>> at.updateRatio(meter.TimeSignature('6/8'))
        >>> at.numberNotesActual, at.numberNotesNormal
        (5, 3)
        '''

        if keySignatureObj == None:
            from music21 import meter   
            ts = meter.TimeSignature('4/4') # default
        else:
            ts = keySignatureObj

        if ts.beatDivisionCount == 3: # if compound
            normalSwitch = 3
        else:
            normalSwitch = 2

        data = self.src.strip()
        if data == '(2':
            a, n = 2, 3 # actual, normal
        elif data == '(3':
            a, n = 3, 2 # actual, normal
        elif data == '(4':
            a, n = 4, 3 # actual, normal
        elif data == '(5':
            a, n = 5, normalSwitch # actual, normal
        elif data == '(6':
            a, n = 6, 2 # actual, normal
        elif data == '(7':
            a, n = 7, normalSwitch # actual, normal
        elif data == '(8':
            a, n = 8, 3 # actual, normal
        elif data == '(9':
            a, n = 9, normalSwitch # actual, normal
        else:       
            raise ABCTokenException('cannot handle tuplet of form: %s' % data)

        self.numberNotesActual = a
        self.numberNotesNormal = n


    def updateNoteCount(self, durationActual=None, durationNormal=None):
        '''Update the note count of notes that are affected by this tuplet.
        '''
        if self.numberNotesActual == None: 
            raise ABCTokenException('must set numberNotesActual with updateRatio()')

        # nee dto 
        from music21 import duration
        self.tupletObj = duration.Tuplet(
            numberNotesActual=self.numberNotesActual, 
            numberNotesNormal=self.numberNotesNormal, 
            durationActual=durationActual,
            durationNormal=durationNormal)

        # copy value; this will be dynamically counted down
        self.noteCount = self.numberNotesActual

        #self.qlRemain = self._tupletObj.totalTupletLength()


class ABCBrokenRhythmMarker(ABCToken):

    # given a logical unit, create an object
    # may be a chord, notes, metadata, bars
    def __init__(self, src):
        ABCToken.__init__(self, src)
        self.data = None

    def __repr__(self):
        return '<ABCBrokenRhythmMarker %r>' % self.src

    def preParse(self):
        '''Called before context adjustments: need to have access to data

        >>> abrm = ABCBrokenRhythmMarker('>>>')
        >>> abrm.preParse()
        >>> abrm.data
        '>>>'
        '''
        self.data = self.src.strip()



class ABCNote(ABCToken):
    '''
    A model of an ABCNote.

    General usage requires multi-pass processing. After being tokenized, each ABCNote needs a number of attributes updates. Attributes to be updated after tokenizing, and based on the linear sequence of tokens: `inBar`, `inBeam`, `inSlur`, `inGrace`, `activeDefaultQuarterLength`, `brokenRhythmMarker`, and `activeKeySignature`.  

    The `chordSymbols` list stores one or more chord symbols (ABC calls these guitar chords) associated with this note. This attribute is updated when parse() is called. 
    '''
    # given a logical unit, create an object
    # may be a chord, notes, bars

    def __init__(self, src=''):
        ABCToken.__init__(self, src)

        # store chord string if connected to this note
        self.chordSymbols = [] 

        # context attributes
        self.inBar = None
        self.inBeam = None
        self.inSlur = None
        self.inGrace = None

        # provide default duration from handler; may change during piece
        self.activeDefaultQuarterLength = None
        # store if a broken symbol applies; pair of symbol, position (left, right)
        self.brokenRhythmMarker = None

        # store key signature for pitch processing; this is an m21 object
        self.activeKeySignature = None

        # store a tuplet if active
        self.activeTuplet = None

        # set to True if a modification of key signautre
        # set to False if an altered tone part of a Key
        self.accidentalDisplayStatus = None
        # determined during parse() based on if pitch chars are present
        self.isRest = None            
        # pitch/ duration attributes for m21 conversion
        # set with parse() based on all other contextual 
        self.pitchName = None # if None, a rest or chord
        self.quarterLength = None


    def __repr__(self):
        return '<ABCNote %r>' % self.src

    
    def _splitChordSymbols(self, strSrc):
        '''Split chord symbols from other string characteristics. Return list of chord symbols and clean, remain chars

        >>> an = ABCNote()
        >>> an._splitChordSymbols('"C"e2')
        (['"C"'], 'e2')
        >>> an._splitChordSymbols('b2')
        ([], 'b2')
        >>> an._splitChordSymbols('"D7""D"d2')
        (['"D7"', '"D"'], 'd2')
        '''
        if '"' in strSrc:
            chordSymbols = reChordSymbol.findall(strSrc)
            # might remove quotes from chord symbols here

            # index of end of last match
            i = [m for m in reChordSymbol.finditer(strSrc)][-1].end()
            return chordSymbols, strSrc[i:]
        else:
            return [], strSrc        


    def _getPitchName(self, strSrc, forceKeySignature=None):
        '''Given a note or rest string without a chord symbol, return a music21 pitch string or None (if a rest), and the accidental display status. This value is paired with an accidental display status. Pitch alterations, and accidental display status, are adjusted if a key is declared in the Note. 

        >>> from music21 import key

        >>> an = ABCNote()
        >>> an._getPitchName('e2')
        ('E5', None)
        >>> an._getPitchName('C')
        ('C4', None)
        >>> an._getPitchName('B,,')
        ('B2', None)
        >>> an._getPitchName('C,')
        ('C3', None)
        >>> an._getPitchName('c')
        ('C5', None)
        >>> an._getPitchName("c'")
        ('C6', None)
        >>> an._getPitchName("c''")
        ('C7', None)
        >>> an._getPitchName("^g")
        ('G#5', True)
        >>> an._getPitchName("_g''")
        ('G-7', True)
        >>> an._getPitchName("=c")
        ('Cn5', True)
        >>> an._getPitchName("z4") 
        (None, None)

        >>> an.activeKeySignature = key.KeySignature(3)
        >>> an._getPitchName("c") # w/ key, change and set to false
        ('C#5', False)

        '''
        try:
            name = rePitchName.findall(strSrc)[0]
        except IndexError: # no matches
            raise ABCHandlerException('cannot find any pitch information in: %s' % repr(strSrc))

        if forceKeySignature != None:
            activeKeySignature = forceKeySignature
        else: # may be None
            activeKeySignature = self.activeKeySignature

        if name == 'z':
            return (None, None) # designates a rest
        else:
            if name.islower():
                octave = 5
            else:
                octave = 4
        # look in source string for register modification
        octModUp = strSrc.count("'")
        octModDown = strSrc.count(",")
        octave -= octModDown
        octave += octModUp

        sharpCount = strSrc.count("^")
        flatCount = strSrc.count("_")
        naturalCount = strSrc.count("=")
        accString = ''
        for x in range(flatCount):
            accString += '-' # m21 symbols
        for x in range(sharpCount):
            accString += '#' # m21 symbols
        for x in range(naturalCount):
            accString += 'n' # m21 symbols

        # if there is an explicit accidental, regardless of key, it should
        # be shown: this works for naturals well
        if accString != '':
            accidentalDisplayStatus = True
        # if we do not have a key signature, and have accidentals, set to None
        elif activeKeySignature == None:
            accidentalDisplayStatus = None
        # pitches are key dependent: accidentals are not given
        # if we have a key and find a name, that does not have a n, must be
        # altered
        else:
            alteredPitches = activeKeySignature.alteredPitches
            # just the steps, no accientals
            alteredPitchSteps = [p.step.lower() for p in alteredPitches]
            # includes #, -
            alteredPitchNames = [p.name.lower() for p in alteredPitches]
            #environLocal.printDebug(['alteredPitches', alteredPitches])

            if name.lower() in alteredPitchSteps:
                # get the corresponding index in the name
                name = alteredPitchNames[alteredPitchSteps.index(name.lower())]
            # set to false, as do not need to show w/ key sig
            accidentalDisplayStatus = False

        pStr = '%s%s%s' % (name.upper(), accString, octave)
        return pStr, accidentalDisplayStatus


    def _getQuarterLength(self, strSrc, forceDefaultQuarterLength=None):
        '''Called with parse(), after context processing, to calculate duration

        >>> an = ABCNote()
        >>> an.activeDefaultQuarterLength = .5
        >>> an._getQuarterLength('e2')
        1.0
        >>> an._getQuarterLength('G')
        0.5
        >>> an._getQuarterLength('=c/2')
        0.25
        >>> an._getQuarterLength('A3/2')
        0.75
        >>> an._getQuarterLength('A/')
        0.25

        >>> an._getQuarterLength('A//')
        0.125
        >>> an._getQuarterLength('A///')
        0.0625

        >>> an = ABCNote()
        >>> an.activeDefaultQuarterLength = .5
        >>> an.brokenRhythmMarker = ('>', 'left')
        >>> an._getQuarterLength('A')
        0.75
        >>> an.brokenRhythmMarker = ('>', 'right')
        >>> an._getQuarterLength('A')
        0.25

        >>> an.brokenRhythmMarker = ('<<<', 'left')
        >>> an._getQuarterLength('A')
        0.0625
        >>> an.brokenRhythmMarker = ('<<<', 'right')
        >>> an._getQuarterLength('A')
        0.9375

        >>> an._getQuarterLength('A', forceDefaultQuarterLength=1)
        1.875

        '''
        if forceDefaultQuarterLength != None:
            activeDefaultQuarterLength = forceDefaultQuarterLength
        else: # may be None
            activeDefaultQuarterLength = self.activeDefaultQuarterLength

        if activeDefaultQuarterLength == None:
            raise ABCTokenException('cannot calculate quarter length without a default quarter length')

        numStr = []
        for c in strSrc:
            if c.isdigit() or c in '/':
                numStr.append(c)
        numStr = ''.join(numStr)
        numStr = numStr.strip()
        # get default
        if numStr == '':
            ql = activeDefaultQuarterLength
        # if only, shorthand for /2
        elif numStr == '/':
            ql = activeDefaultQuarterLength * .5
        elif numStr == '//':
            ql = activeDefaultQuarterLength * .25
        elif numStr == '///':
            ql = activeDefaultQuarterLength * .125
        # if a half fraction
        elif numStr.startswith('/'):
            ql = activeDefaultQuarterLength / int(numStr.split('/')[1])
        # uncommon usage: 3/ short for 3/2
        elif numStr.endswith('/'):
            n = int(numStr.split('/')[0].strip())
            d = 2
            ql = activeDefaultQuarterLength * (float(n) / d)

        # assume we have a complete fraction
        elif '/' in numStr:
            n, d = numStr.split('/')
            n = int(n.strip())
            d = int(d.strip())
            ql = activeDefaultQuarterLength * (float(n) / d)
        # not a fraction; a multiplier
        else: 
            ql = activeDefaultQuarterLength * int(numStr)

        if self.brokenRhythmMarker != None:
            symbol, direction = self.brokenRhythmMarker
            if symbol == '>':
                modPair = (1.5, .5)
            elif symbol == '<':
                modPair = (.5, 1.5)
            elif symbol == '>>':
                modPair = (1.75, .25)
            elif symbol == '<<':
                modPair = (.25, 1.75)
            elif symbol == '>>>':
                modPair = (1.875, .125)
            elif symbol == '<<<':
                modPair = (.125, 1.875)
            # apply based on direction
            if direction == 'left':
                ql *= modPair[0]
            elif direction == 'right':
                ql *= modPair[1]

        # need to look at tuplets lastly
        if self.activeTuplet != None: # this is an m21 tuplet object
            # set the underlying duration type; probably this duration?
            # or the activeDefaultQuarterLength
            self.activeTuplet.setDurationType(activeDefaultQuarterLength)
            # scale duration by active tuplet multipler
            ql *= self.activeTuplet.tupletMultiplier()
        return ql


    def parse(self, forceKey=None, forceDefaultQuarterLength=None, 
            forceKeySignature=None):
        self.chordSymbols, nonChordSymStr = self._splitChordSymbols(self.src)        
        # get pitch name form remaining string
        # rests will have a pitch name of None
        a, b = self._getPitchName(nonChordSymStr,
               forceKeySignature=forceKeySignature)
        self.pitchName, self.accidentalDisplayStatus = a, b

        if self.pitchName == None:
            self.isRest = True
        else:
            self.isRest = False

        self.quarterLength = self._getQuarterLength(nonChordSymStr, 
                            forceDefaultQuarterLength=forceDefaultQuarterLength)

        # environLocal.printDebug(['ABCNote:', 'pitch name:', self.pitchName, 'ql:', self.quarterLength])


class ABCChord(ABCNote):
    '''
    A representation of an ABC Chord, which contains within its delimiters individual notes. 

    A subclass of ABCNote. 

    '''
    # given a logical unit, create an object
    # may be a chord, notes, bars

    def __init__(self, src):
        ABCNote.__init__(self, src)
        # store a list of component objects
        self.subTokens = []

    def __repr__(self):
        return '<ABCChord %r>' % self.src


    def parse(self, forceKey=None, forceDefaultQuarterLength=None):
        self.chordSymbols, nonChordSymStr = self._splitChordSymbols(self.src) 

        tokenStr = nonChordSymStr[1:-1] # remove outer brackets
        #environLocal.printDebug(['ABCChord:', nonChordSymStr, 'tokenStr', tokenStr])

        self.quarterLength = self._getQuarterLength(nonChordSymStr, 
            forceDefaultQuarterLength=forceDefaultQuarterLength)

        # create a handler for processing internal chord notes
        ah = ABCHandler()
        # only tokenizing; not calling process() as these objects
        # have no metadata
        # may need to supply key?
        ah.tokenize(tokenStr)

        chordDurationPost = None
        for t in ah.tokens:
            #environLocal.printDebug(['ABCChord: subTokens', t])
            # parse any tokens individually, supply local data as necesssary
            if isinstance(t, ABCNote):
                t.parse(
                    forceDefaultQuarterLength=self.activeDefaultQuarterLength,
                    forceKeySignature=self.activeKeySignature)
                # get the quarter length from the sub-tokens
                # note: assuming these are the same
                chordDurationPost = t.quarterLength

            self.subTokens.append(t)

        if chordDurationPost != None:
            self.quarterLength = chordDurationPost


#-------------------------------------------------------------------------------
class ABCHandler(object):

    # divide elements of a character stream into objects and handle
    # store in a list, and pass global information to compontns
    def __init__(self):
        # tokens are ABC objects in a linear stream
        self._tokens = []

    def _getLinearContext(self, strSrc, i):
        '''Find the local context of a string or list of ojbects. Returns charPrevNotSpace, charPrev, charThis, charNext, charNextNotSpace.


        >>> ah = ABCHandler()
        >>> ah._getLinearContext('12345', 0)
        (None, None, '1', '2', '2', '3')
        >>> ah._getLinearContext('12345', 1)
        ('1', '1', '2', '3', '3', '4')
        >>> ah._getLinearContext('12345', 3)
        ('3', '3', '4', '5', '5', None)
        >>> ah._getLinearContext('12345', 4)
        ('4', '4', '5', None, None, None)

        >>> ah._getLinearContext([32, None, 8, 11, 53], 4)
        (11, 11, 53, None, None, None)
        >>> ah._getLinearContext([32, None, 8, 11, 53], 2)
        (32, None, 8, 11, 11, 53)
        >>> ah._getLinearContext([32, None, 8, 11, 53], 0)
        (None, None, 32, None, 8, 8)


        '''            
        lastIndex = len(strSrc) - 1
        if i > lastIndex:
            raise ABCHandlerException
        # find local area of string
        if i > 0:
            cPrev = strSrc[i-1]
        else:      
            cPrev = None
        # get last char previous non-white; do not start with current
        # -1 goes to index 0
        cPrevNotSpace = None
        for j in range(i-1, -1, -1):
            # condition to break: find a something that is not None, or 
            # a string that is not a space
            if isinstance(strSrc[j], str):
                if not strSrc[j].isspace():
                    cPrevNotSpace = strSrc[j]
                    break
            else:
                if strSrc[j] != None:
                    cPrevNotSpace = strSrc[j]
                    break
        # set this characters
        c = strSrc[i]

        cNext = None
        if i < len(strSrc)-1:
            cNext = strSrc[i+1]            

        # get 2 chars forward
        cNextNext = None
        if i < len(strSrc)-2:
            cNextNext = strSrc[i+2]

        cNextNotSpace = None
        # start at next index and look forward
        for j in range(i+1, len(strSrc)):
            if isinstance(strSrc[j], str):
                if not strSrc[j].isspace():
                    cNextNotSpace = strSrc[j]
                    break
            else:
                if strSrc[j] != None:
                    cNextNotSpace = strSrc[j]
                    break
        return cPrevNotSpace, cPrev, c, cNext, cNextNotSpace, cNextNext


    def _getNextLineBreak(self, strSrc, i):
        '''Return index of next line break.

        >>> ah = ABCHandler()
        >>> strSrc = 'de  we\\n wer bfg\\n'
        >>> ah._getNextLineBreak(strSrc, 0)
        6
        >>> strSrc[0:6]
        'de  we'
        >>> # from last line break
        >>> ah._getNextLineBreak(strSrc, 6)
        15
        >>> strSrc[ah._getNextLineBreak(strSrc, 0):]
        '\\n wer bfg\\n'
        '''
        lastIndex = len(strSrc) - 1
        j = i + 1 # start with next
        while True:
            if strSrc[j] == '\n' or j > lastIndex:
                return j # will increment to next char on loop
            j += 1


    #---------------------------------------------------------------------------
    # token processing

    def tokenize(self, strSrc):
        '''Walk the abc string, creating ABC objects along the way.

        This may be called separately from process(), in the case that pre/post parse processing is not needed. 
        '''
        i = 0
        collect = []
        lastIndex = len(strSrc) - 1

        activeChordSymbol = '' # accumulate, then prepend
        while True:    
            if i > lastIndex:
                break

            q = self._getLinearContext(strSrc, i)
            cPrevNotSpace, cPrev, c, cNext, cNextNotSpace, cNextNext = q
            
            # comment lines, also encoding defs
            if c == '%':
                j = self._getNextLineBreak(strSrc, i)
                #environLocal.printDebug(['got comment:', repr(strSrc[i:j+1])])
                i = j+1 # skip \n char
                continue

            # metadata: capatal alpha, with next char as ':'
            # or w: (lyric defs)
            # some meta data might have bar symbols, for example
            # need to not misinterpret repeat bars as meta
            # e.g. dAG FED:|2 dAG FGA| this is incorrect, but can avoid by
            # looking for a leading pipe
            if (((c.isalpha() and c.isupper()) or c in 'w')
                and cNext != None and cNext == ':' and 
                cNextNext != None and cNextNext not in '|'):
                # collect until end of line; add one to get line break
                j = self._getNextLineBreak(strSrc, i) + 1
                collect = strSrc[i:j].strip()
                #environLocal.printDebug(['got metadata:', repr(''.join(collect))])
                self._tokens.append(ABCMetadata(collect))
                i = j
                continue
            
            # get bars: if not a space and not alphanemeric
            if (not c.isspace() and not c.isalnum()
                and c not in ['~', '(']):
                matchBars = False
                for barIndex in range(len(ABC_BARS)):
                    # first of bars tuple is symbol to match
                    if c + cNext == ABC_BARS[barIndex][0]:
                        j = i + 2
                        matchBars = True 
                        break
                    # check for single char bars
                    elif c == ABC_BARS[barIndex][0]:
                        j = i + 1
                        matchBars = True 
                        break
                if matchBars:
                    collect = strSrc[i:j]
                    #environLocal.printDebug(['got bars:', repr(collect)])  
                    self._tokens.append(ABCBar(collect))
                    i = j
                    continue
                    
            # get tuplet indicators: (2, (3
            # TODO: extended tuplets look like this: (p:q:r or (3::
            if (c == '(' and cNext != None and cNext.isdigit()):
                j = i + 2 # always two characters
                collect = strSrc[i:j]
                #environLocal.printDebug(['got tuplet start:', repr(collect)])
                self._tokens.append(ABCTuplet(collect))
                i = j
                continue

            # get broken rhythm modifiers: < or >, >>, up to <<<
            if c in '<>':
                j = i + 1
                while (j < lastIndex and strSrc[j] in '<>'):
                    j += 1
                collect = strSrc[i:j]
                #environLocal.printDebug(['got bidrectional rhythm mod:', repr(collect)])
                self._tokens.append(ABCBrokenRhythmMarker(collect))
                i = j
                continue

            # get chord symbols / guitar chords; collected and joined with
            # chord or notes
            if (c == '"'):
                j = i + 1
                while (j < lastIndex and strSrc[j] not in '"'):
                    j += 1
                j += 1 # need character that caused break
                # there may be more than one chord symbol: need to accumulate
                activeChordSymbol += strSrc[i:j]
                #environLocal.printDebug(['got chord symbol:', repr(activeChordSymbol)])
                i = j
                continue

            # get chords
            if (c == '['):
                j = i + 1
                while (j < lastIndex and strSrc[j] not in ']'):
                    j += 1
                j += 1 # need character that caused break
                # prepend chord symbol
                if activeChordSymbol != '':
                    collect = activeChordSymbol+strSrc[i:j]
                    activeChordSymbol = '' # reset
                else:
                    collect = strSrc[i:j]

                #environLocal.printDebug(['got chord:', repr(collect)])
                self._tokens.append(ABCChord(collect))

                i = j
                continue

            # get the start of a note event: alpha, or 
            # ~ tunr/ornament, accidentals ^, =, - as well as ^^
            if (c.isalpha() or c in '~^=_.'):
                # condition where we start with an alpha that is not an alpha
                # that comes before a pitch indication
                # H is fermata, L is accent, T is trill
                foundPitchAlpha = c.isalpha() and c not in 'uvHLT'
                j = i + 1

                while True:
                    if j > lastIndex:
                        break    
                    # if we have not found pitch alpha
                    # ornaments may precede note names
                    # accidentals (^=_) staccato (.), up/down bow (u, v)
                    elif foundPitchAlpha == False and strSrc[j] in '~=^_.uvHLT':
                        j += 1
                        continue                    
                    # only allow one pitch alpha to be a continue condition
                    elif (foundPitchAlpha == False and strSrc[j].isalpha() 
                        and strSrc[j] not in 'uvHL'):
                        foundPitchAlpha = True
                        j += 1
                        continue                    
                    # continue conditions after alpha: 
                    # , register modifiaciton (, ') or number, rhythm indication
                    # number, /, 
                    elif strSrc[j].isdigit() or strSrc[j] in ',/\'':
                        j += 1
                        continue    
                    else: # space, all else: break
                        break
                # prepend chord symbol
                if activeChordSymbol != '':
                    collect = activeChordSymbol+strSrc[i:j]
                    activeChordSymbol = '' # reset
                else:
                    collect = strSrc[i:j]
                #environLocal.printDebug(['got note event:', repr(collect)])
                self._tokens.append(ABCNote(collect))
                i = j
                continue

            # look for white space: can be used to determine beam groups

            # no action: normal continuation of 1 char
            i += 1

    
    def tokenProcess(self):
        '''Process all token objects. First, call preParse(), then do cointext assignments, then call parse(). 
        '''
        # need a key object to get altered pitches
        from music21 import key

        # pre-parse : call on objects that need preliminary processing
        # metadata, for example, is parsed
        lastTimeSignature = None
        for t in self._tokens:
            #environLocal.printDebug(['token:', t.src])
            t.preParse()

        # context: iterate through tokens, supplying contextual data as necessary to appropriate objects
        lastDefaultQL = None
        lastKeySignature = None
        lastTimeSignatureObj = None # an m21 object
        lastTupletToken = None # a token obj; keeps count of usage

        for i in range(len(self._tokens)):
            # get context of tokens
            q = self._getLinearContext(self._tokens, i)
            tPrevNotSpace, tPrev, t, tNext, tNextNotSpace, tNextNext = q
            
            if isinstance(t, ABCMetadata):
                if t.isMeter():
                    lastTimeSignatureObj = t.getTimeSignatureObject()
                # restart matching conditions; match meter twice ok
                if t.isMeter() or t.isDefaultNoteLength():
                    lastDefaultQL = t.getDefaultQuarterLength()
                elif t.isKey():
                    sharpCount, mode = t.getKeySignature()
                    lastKeySignature = key.KeySignature(sharpCount, mode)
                continue
            # broken rhythms need to be applied to previous and next notes
            if isinstance(t, ABCBrokenRhythmMarker):
                if (isinstance(tPrev, ABCNote) and 
                isinstance(tNext, ABCNote)):
                    #environLocal.printDebug(['tokenProcess: got broken rhythm marker', t.src])       
                    tPrev.brokenRhythmMarker = (t.data, 'left')
                    tNext.brokenRhythmMarker = (t.data, 'right')
                else:
                    raise ABCHandlerException('broken rhythm marker (%s) not positioned between two notes or chords' % t.src)

            # need to update tuplets with currently active meter
            if isinstance(t, ABCTuplet):
                t.updateRatio(lastTimeSignatureObj)
                # set number of notes that will be altered
                # might need to do this with ql values, or look ahead to nxt 
                # token
                t.updateNoteCount() 
                lastTupletToken = t

            # ABCChord inherits ABCNote, thus getting note is enough for both
            if isinstance(t, (ABCNote, ABCChord)):
                if lastDefaultQL == None:
                    raise ABCHandlerException('no active default note length provided for note processing. tPrev: %s, t: %s, tNext: %s' % (tPrev, t, tNext))
                t.activeDefaultQuarterLength = lastDefaultQL
                t.activeKeySignature = lastKeySignature
                t.activeKeySignature = lastKeySignature

                if lastTupletToken == None:
                    pass
                elif lastTupletToken.noteCount == 0:
                    lastTupletToken = None # clear, no longer needed
                else:
                    lastTupletToken.noteCount -= 1 # decrement
                    # add a reference to the note
                    t.activeTuplet = lastTupletToken.tupletObj

        # parse : call methods to set attributes and parse string
        for t in self._tokens:
            t.parse()

            #print o.src

    def process(self, strSrc):
        self._tokens = []
        self.tokenize(strSrc)
        self.tokenProcess()
        # return list of tokens; stored internally

    def _getTokens(self):
        if self._tokens == []:
            raise ABCHandlerException('must process tokens before calling split')
        return self._tokens

    tokens = property(_getTokens, 
        doc = '''Get a the tokens from this Handler
        ''')
    

    #---------------------------------------------------------------------------
    # utility methods for post processing

    def splitByVoice(self):
        '''Given a processed token list, look for voices. If voices exist, split into parts: common metadata, then next voice, next voice, etc.

        >>> abcStr = 'M:6/8\\nL:1/8\\nK:G\\nV:1 name="Whistle" snm="wh"\\nB3 A3 | G6 | B3 A3 | G6 ||\\nV:2 name="violin" snm="v"\\nBdB AcA | GAG D3 | BdB AcA | GAG D6 ||\\nV:3 name="Bass" snm="b" clef=bass\\nD3 D3 | D6 | D3 D3 | D6 ||'
        >>> ah = ABCHandler()
        >>> junk = ah.process(abcStr)
        >>> tokenColls = ah.splitByVoice()
        >>> [t.src for t in tokenColls[0]] # common headers are first
        ['M:6/8', 'L:1/8', 'K:G']
        >>> # then each voice
        >>> [t.src for t in tokenColls[1]] 
        ['V:1 name="Whistle" snm="wh"', 'B3', 'A3', '|', 'G6', '|', 'B3', 'A3', '|', 'G6', '||']
        >>> [t.src for t in tokenColls[2]] 
        ['V:2 name="violin" snm="v"', 'B', 'd', 'B', 'A', 'c', 'A', '|', 'G', 'A', 'G', 'D3', '|', 'B', 'd', 'B', 'A', 'c', 'A', '|', 'G', 'A', 'G', 'D6', '||']
        >>> [t.src for t in tokenColls[3]] 
        ['V:3 name="Bass" snm="b" clef=bass', 'D3', 'D3', '|', 'D6', '|', 'D3', 'D3', '|', 'D6', '||']

        '''

        # TODO: this procedure should also be responsible for 
        # breaking the passage into voice/lyric pairs

        if self._tokens == []:
            raise ABCHandlerException('must process tokens before calling split')

        voiceCount = 0
        pos = []
        for i in range(len(self._tokens)):
            t = self._tokens[i]
            if isinstance(t, ABCMetadata):
                if t.isVoice():
                    # if first char is a number
                    # can be V:3 name="Bass" snm="b" clef=bass
                    if t.data[0].isdigit():
                        pos.append(i) # store position 
                        voiceCount += 1

        post = []
        # no voices, or definition of one voice, or use of V: field for 
        # something else
        if voiceCount <= 1:
            post.append(self._tokens)
        # two or more voices
        else: 
            # metadata is everything before first v1. 
            # first v1 found at pos[0]
            post.append(self._tokens[:pos[0]])
            i = pos[0]
            # start range at second value in pos
            for x in range(1, len(pos)):
                j = pos[x]
                post.append(self._tokens[i:j])
                i = j
            # get last span
            post.append(self._tokens[i:])

        return post



    def getTitle(self):
        '''If tokens are processed, get the first title tag. Used for testing.
        '''
        if self._tokens == []:
            raise ABCHandlerException('must process tokens before calling split')
        for t in self._tokens:
            if isinstance(t, ABCMetadata):
                if t.isTitle():
                    return t.data
        return None




#-------------------------------------------------------------------------------
class ABCFile(object):
    '''
    ABC File access

    '''
    
    def __init__(self): 
        pass

    def open(self, filename): 
        '''Open a file for reading
        '''
        self.file = open(filename, 'r') 

    def openFileLike(self, fileLike):
        '''Assign a file-like object, such as those provided by StringIO, as an open file object.

        >>> fileLikeOpen = StringIO.StringIO()
        '''
        self.file = fileLike
    
    def __repr__(self): 
        r = "<ABCFile>" 
        return r 
    
    def close(self): 
        self.file.close() 
    
    def read(self): 
        return self.readstr(self.file.read()) 
    
    def readstr(self, str): 
        handler = ABCHandler()
        # return the handler instanc
        handler.process(str)
        return handler
    
#     def write(self): 
#         ws = self.writestr()
#         self.file.write(ws) 
#     
#     def writestr(self): 
#         pass










#-------------------------------------------------------------------------------
class Test(unittest.TestCase):

    def runTest(self):
        pass

    def testTokenization(self):
        from music21.abc import testFiles

        for (tf, countTokens, noteTokens, chrodTokens) in [
            (testFiles.fyrareprisarn, 236, 152, 0), 
            (testFiles.mysteryReel, 188, 153, 0), 
            (testFiles.aleIsDear, 291, 206, 32),
            (testFiles.testPrimitive, 94, 75, 2),
            (testFiles.kitchGirl, 125, 101, 2),
            (testFiles.williamAndNancy, 127, 93, 0),
            (testFiles.morrisonsJig, 176, 137, 0),

                ]:

            handler = ABCHandler()
            handler.tokenize(tf)
            tokens = handler._tokens # get private for testing
            self.assertEqual(len(tokens), countTokens)
            countNotes = 0
            countChords = 0
            for o in tokens:
                if isinstance(o, ABCChord):
                    countChords += 1
                elif isinstance(o, ABCNote):
                    countNotes += 1

            self.assertEqual(countNotes, noteTokens)
            self.assertEqual(countChords, chrodTokens)
        

    def testRe(self):

        src = 'A: this is a test'
        post = reMetadataTag.match(src).end()
        self.assertEqual(src[:post], 'A:')
        self.assertEqual(src[post:], ' this is a test' )


        src = 'Q: this is a test % and a following comment'
        post = reMetadataTag.match(src).end()
        self.assertEqual(src[:post], 'Q:')


        # chord symbol matches
        src = 'd|"G"e2d B2d|"C"gfe "D7"d2d|"G"e2d B2d|"A7""C"gfe "D7""D"d2c|'
        post = reChordSymbol.findall(src)
        self.assertEqual(post, ['"G"', '"C"', '"D7"', '"G"', '"A7"', 
                                '"C"', '"D7"', '"D"'] )

        # get index of last match of many
        i = [m for m in reChordSymbol.finditer(src)][-1].end()

        src = '=d2'
        self.assertEqual(rePitchName.findall(src)[0], 'd')

        src = 'A3/2'
        self.assertEqual(rePitchName.findall(src)[0], 'A')



    def testTokenProcessMetadata(self):
        from music21.abc import testFiles

#'Full Rigged Ship', '6/8', 'G'
        for (tf, titleEncoded, meterEncoded, keyEncoded) in [
            (testFiles.fyrareprisarn, 'Fyrareprisarn', '3/4', 'F'), 
            (testFiles.mysteryReel, 'Mystery Reel', 'C|', 'G'), 
            (testFiles.aleIsDear, 'Ale is Dear, the', '4/4', 'D', ),
            (testFiles.kitchGirl, 'Kitchen Girl', '4/4', 'D'),
            (testFiles.williamAndNancy, 'William and Nancy', '6/8', 'G'),
            ]:

            handler = ABCHandler()
            handler.tokenize(tf)
            handler.tokenProcess()

            tokens = handler._tokens # get private for testing
            for t in tokens:
                if isinstance(t, ABCMetadata):
                    if t.tag == 'T':
                        self.assertEqual(t.data, titleEncoded)
                    elif t.tag == 'M':
                        self.assertEqual(t.data, meterEncoded)
                    elif t.tag == 'K':
                        self.assertEqual(t.data, keyEncoded)



    def testTokenProcess(self):
        from music21.abc import testFiles

        for tf in [
            testFiles.fyrareprisarn,
            testFiles.mysteryReel,
            testFiles.aleIsDear, 
            testFiles.testPrimitive,
            testFiles.kitchGirl,
            testFiles.williamAndNancy,
            ]:

            handler = ABCHandler()
            handler.tokenize(tf)
            handler.tokenProcess()


    def testNoteParse(self):
        from music21 import key

        an = ABCNote()

        # with a key signature, matching steps are assumed altered
        an.activeKeySignature = key.KeySignature(3)
        self.assertEqual(an._getPitchName("c"), ('C#5', False))

        an.activeKeySignature = None
        self.assertEqual(an._getPitchName("c"), ('C5', None))
        self.assertEqual(an._getPitchName("^c"), ('C#5', True))


        an.activeKeySignature = key.KeySignature(-3)
        self.assertEqual(an._getPitchName("B"), ('B-4', False))

        an.activeKeySignature = None
        self.assertEqual(an._getPitchName("B"), ('B4', None))
        self.assertEqual(an._getPitchName("_B"), ('B-4', True))




if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1: # normal conditions
        music21.mainTest(Test)
    elif len(sys.argv) > 1:
        t = Test()

        t.testNoteParse()








