#!/usr/bin/python
#-------------------------------------------------------------------------------
# Name:         possibility.py
# Purpose:      music21 class to define a possibility (possible resolution) for a note
# Authors:      Jose Cabal-Ugaz
#
# Copyright:    (c) 2011 The music21 Project    
# License:      LGPL
#-------------------------------------------------------------------------------

import music21
import unittest

from music21 import pitch
from music21 import voiceLeading
from music21 import interval
from music21 import environment

from music21.figuredBass import rules

_MOD = "possibility.py"

class Possibility(dict):
    # CHORD FORMATION RULES
    def isCorrectlyFormed(self, pitchNamesToHave = None, fbRules = rules.Rules(), verbose = False):
        # Imitates checkChord() from rules.py, but one calls the method on the Possibility object,
        # rather than providing the pitches as an argument and calling a Rules object.
        '''
        >>> from music21 import *
        >>> from music21.figuredBass import rules
        >>> from music21.figuredBass import possibility
        >>> fbRules = rules.Rules()
        >>> pitchNames = ['C','E','G']
        >>> p1 = possibility.Possibility({'S': pitch.Pitch('C5'), 'A': pitch.Pitch('G4'), 'T': pitch.Pitch('E4'), 'B': pitch.Pitch('C3')})
        >>> p1.isCorrectlyFormed(pitchNames, fbRules)
        True
        >>> p1['T'] = pitch.Pitch('C3')
        >>> p1.isCorrectlyFormed(pitchNames, fbRules)
        False
        '''
        correctlyFormed = True
        
        if not fbRules.allowIncompletePossibilities:
            if pitchNamesToHave is None:
                raise PossibilityException("Pitch names to analyze completeness not provided.")
            if self.isIncomplete(pitchNamesToHave, verbose):
                correctlyFormed = False
                if not verbose:
                    return correctlyFormed
        if fbRules.topVoicesWithinOctave:
            if not self.topVoicesWithinOctave(verbose):
                correctlyFormed = False
                if not verbose:
                    return correctlyFormed
        
        return correctlyFormed
    
    def isIncomplete(self, pitchNamesToHave, verbose = False):
        '''
        A possibility is incomplete if it doesn't contain at least
        one of each pitch name.
        
        >>> from music21 import *
        >>> from music21.figuredBass import possibility
        >>> pitchNames = ['C','E','G']
        >>> p1 = possibility.Possibility({'S': pitch.Pitch('C5'), 'A': pitch.Pitch('G4'), 'T': pitch.Pitch('E4'), 'B': pitch.Pitch('C3')})
        >>> p1.isIncomplete(pitchNames)
        False
        >>> p1['T'] = pitch.Pitch('C4')
        >>> p1.isIncomplete(pitchNames)
        True
        '''
        pitchNamesContained = []
        for voiceLabel in self.keys():
            if self[voiceLabel].name not in pitchNamesContained:
                pitchNamesContained.append(self[voiceLabel].name)
        pitchNamesContained.sort()
        pitchNamesToHave.sort()
        if not cmp(pitchNamesContained, pitchNamesToHave):
            return False
        else:
            if verbose:
                environRules = environment.Environment(_MOD)
                environRules.warn("Incomplete Chord!")
            return True
    
    def topVoicesWithinOctave(self, verbose = False):
        '''
        Returns true if upper voices are found within an octave of each other.
        
        >>> from music21 import *
        >>> from music21.figuredBass import possibility
        >>> p1 = possibility.Possibility({'S': pitch.Pitch('C5'), 'A': pitch.Pitch('G4'), 'T': pitch.Pitch('E4'), 'B': pitch.Pitch('C3')})
        >>> p1.topVoicesWithinOctave()
        True
        >>> p1['T'] = pitch.Pitch('E3')
        >>> p1.topVoicesWithinOctave()
        False
        '''
        topVoicesWithinAnOctave = True
        pitchesContained = []
        for voiceLabel in self.keys():
            pitchesContained.append((self[voiceLabel], voiceLabel))
        pitchesContained.sort()
        
        for pitch1Index in range(1, len(pitchesContained)):
            for pitch2Index in range(pitch1Index, len(pitchesContained)):
                (pitch1, vl1) = pitchesContained[pitch1Index]
                (pitch2, vl2) = pitchesContained[pitch2Index]
                if abs(interval.notesToGeneric(pitch1, pitch2).value) > 8:
                    if verbose:
                        environRules = environment.Environment(_MOD)
                        environRules.warn(vl1 + " and " + vl2 + " are greater than an octave apart.")
                    topVoicesWithinAnOctave = False
                    if not verbose:
                        return topVoicesWithinAnOctave
        
        return topVoicesWithinAnOctave

    # VOICE LEADING RULES
    def hasCorrectVoiceLeading(self, consequentPossibility, fbRules = rules.Rules(), verbose = False):
        # Imitates checkVoiceLeading() from rules.py, BUT it has the added advantage
        # of being able to be used for 2 -> n voices.
        # Also imitates checkChords() for checking of hidden fifths/hidden octaves
        '''
        Returns True if all voicing rules as specified in the rules object are followed
        in the progression of one possibility to another. This encompasses parallel fifths, 
        parallel octaves, and voice leaps.
        
        Note that the consequent possibility need not have all the voices of the previous
        possibility. What matters is that all the voices in the consequent possibility
        be found in the previous possibility. For example, having {'S','A','T','B'} as 
        a previous possibility and then having {'T','B'} as the consequent possibility
        is OK. The method will then check the voice leading of only 'T' and 'B'.
        
        >>> from music21 import *
        >>> from music21.figuredBass import rules
        >>> from music21.figuredBass import possibility
        >>> fbRules = rules.Rules()
        >>> p1 = possibility.Possibility({'Tenor': pitch.Pitch('G3'), 'Bass': pitch.Pitch('C3'), 'Soprano': pitch.Pitch('C5')})
        >>> p2 = possibility.Possibility({'Tenor': pitch.Pitch('A3'), 'Bass': pitch.Pitch('D3')})
        >>> p1.hasCorrectVoiceLeading(p2, fbRules)
        False
        >>> p1['Tenor'] = pitch.Pitch('C4')
        >>> p2['Tenor'] = pitch.Pitch('D4')
        >>> p1.hasCorrectVoiceLeading(p2, fbRules)
        False
        >>> p1['Tenor'] = pitch.Pitch('F3')
        >>> p2['Tenor'] = pitch.Pitch('G3')
        >>> p1.hasCorrectVoiceLeading(p2, fbRules)
        True
        >>> p2['Bass'] = pitch.Pitch('C5')
        >>> p1.hasCorrectVoiceLeading(p2, fbRules)
        False
        '''
        if verbose:
            environRules = environment.Environment(_MOD)
            
        hasCorrectVoiceLeading = True
        voiceQuartets = self._findVoiceQuartets(consequentPossibility)

        for (pitchA1, pitchA2, vl1, pitchB1, pitchB2, vl2) in voiceQuartets:
            vlq = voiceLeading.VoiceLeadingQuartet(pitchA1, pitchA2, pitchB1, pitchB2)
            if not fbRules.allowParallelFifths:
                if vlq.parallelFifth():
                    if verbose:
                        environRules.warn("Parallel fifths between " + vl1 + " and " + vl2 + ".")
                    hasCorrectVoiceLeading = False
                    if not verbose:
                        return hasCorrectVoiceLeading
            if not fbRules.allowParallelOctaves:
                if vlq.parallelOctave():
                    if verbose:
                        environRules.warn("Parallel octaves between " + vl1 + " and " + vl2 + ".")
                    hasCorrectVoiceLeading = False
                    if not verbose:
                        return hasCorrectVoiceLeading
        
        voicePairs = self._findVoicePairs(consequentPossibility)        
        voicePairs.sort()

        (v0n1, v0n2, vl) = voicePairs[0]
        if abs(v0n1.ps - v0n2.ps) > (12.0 * fbRules.bottomVoiceLeapOctaveLimit):
            if verbose:
                environRules.warn("Voice leap in " + vl + " voice.")
            hasCorrectVoiceLeading = False
            if not verbose:
                return hasCorrectVoiceLeading
            
        for voiceIndex in range(1, len(voicePairs)):
            (v1n1, v1n2, vl) = voicePairs[voiceIndex]
            if abs(v1n1.ps - v1n2.ps) > (12.0 * fbRules.topVoiceLeapOctaveLimit):
                if verbose:
                    environRules.warn("Voice leap in " + vl + " voice.")
                hasCorrectVoiceLeading = False
                if not verbose:
                    return hasCorrectVoiceLeading
                  
        return hasCorrectVoiceLeading

    def containsParallelFifths(self, consequentPossibility, verbose = False):
        '''
        Checks for parallel fifths between self and a consequent possibility.
        
        >>> from music21 import *
        >>> from music21.figuredBass import possibility
        >>> p1 = possibility.Possibility({'Tenor': pitch.Pitch('G3'), 'Bass': pitch.Pitch('C3')})
        >>> p2 = possibility.Possibility({'Tenor': pitch.Pitch('A3'), 'Bass': pitch.Pitch('D3')})
        >>> p1.containsParallelFifths(p2)
        True
        ''' 
        hasParallelFifth = False
        voiceQuartets = self._findVoiceQuartets(consequentPossibility)
        
        for (pitchA1, pitchA2, vl1, pitchB1, pitchB2, vl2) in voiceQuartets:
            vlq = voiceLeading.VoiceLeadingQuartet(pitchA1, pitchA2, pitchB1, pitchB2)
            if vlq.parallelFifth():
                if verbose:
                    environRules = environment.Environment(_MOD)
                    environRules.warn("Parallel fifths between " + vl1 + " and " + vl2 + ".")
                hasParallelFifth = True
                if not verbose:
                    return hasParallelFifth
        
        return hasParallelFifth
        
    def containsParallelOctaves(self, consequentPossibility, verbose = False):
        '''
        Checks for parallel fifths between self and a consequent possibility.
        
        >>> from music21 import *
        >>> from music21.figuredBass import possibility
        >>> p1 = possibility.Possibility({'Tenor': pitch.Pitch('C4'), 'Bass': pitch.Pitch('C3')})
        >>> p2 = possibility.Possibility({'Tenor': pitch.Pitch('D4'), 'Bass': pitch.Pitch('D3')})
        >>> p1.containsParallelOctaves(p2)
        True
        '''        
        hasParallelOctave = False
        voiceQuartets = self._findVoiceQuartets(consequentPossibility)
        
        for (pitchA1, pitchA2, vl1, pitchB1, pitchB2, vl2) in voiceQuartets:
            vlq = voiceLeading.VoiceLeadingQuartet(pitchA1, pitchA2, pitchB1, pitchB2)
            if vlq.parallelOctave():
                if verbose:
                    environRules = environment.Environment(_MOD)
                    environRules.warn("Parallel octaves between " + vl1 + " and " + vl2 + ".")
                hasParallelOctave = True
                if not verbose:
                    return hasParallelOctave
        
        return hasParallelOctave
    
    # HIDDEN INTERVAL RULES
    def checkHiddenIntervals(self, consequentPossibility, vlTop, vlBottom, fbRules = rules.Rules(), verbose = False):
        '''
        Checks for hidden fifths and octaves between self and a consequent possibility, as specified in fbRules. 
        To remove ambiguities, asked to provide the key of the top voice and the key of the bottom voice.
        
        >>> from music21 import *
        >>> from music21.figuredBass import possibility
        >>> from music21.figuredBass import rules
        >>> fbRules = rules.Rules()
        >>> p1 = possibility.Possibility({'Soprano': pitch.Pitch('E5'), 'Bass': pitch.Pitch('C3'), 'Tenor': pitch.Pitch('G4')})
        >>> p2 = possibility.Possibility({'Soprano': pitch.Pitch('A5'), 'Bass': pitch.Pitch('D3'), 'Tenor': pitch.Pitch('F4')})
        >>> p1.checkHiddenIntervals(p2, 'Soprano', 'Bass', fbRules)
        False
        >>> p1['Soprano'] = pitch.Pitch('A5')
        >>> p2['Soprano'] = pitch.Pitch('D6')
        >>> p1.checkHiddenIntervals(p2, 'Soprano', 'Bass', fbRules)
        False
        '''
        hasNoHiddenIntervals = True
        
        if not fbRules.allowHiddenFifths:
            hasHiddenFifth = self.containsHiddenFifth(consequentPossibility, vlTop, vlBottom, verbose)
            if hasHiddenFifth:
                hasNoHiddenIntervals = False
                if not verbose:
                    return hasNoHiddenIntervals
        if not fbRules.allowHiddenOctaves:
            hasHiddenOctave = self.containsHiddenOctave(consequentPossibility, vlTop, vlBottom, verbose)
            if hasHiddenOctave:
                hasNoHiddenIntervals = False
                if not verbose:
                    return hasNoHiddenIntervals
        
        return hasNoHiddenIntervals
        
    def containsHiddenFifth(self, consequentPossibility, vlTop, vlBottom, verbose = False):
        '''
        Checks for hidden fifths between self and a consequent possibility. To remove ambiguities,
        asked to provide the key of the top voice and the key of the bottom voice.
        
        >>> from music21 import *
        >>> from music21.figuredBass import possibility
        >>> p1 = possibility.Possibility({'Soprano': pitch.Pitch('E5'), 'Bass': pitch.Pitch('C3')})
        >>> p2 = possibility.Possibility({'Soprano': pitch.Pitch('A5'), 'Bass': pitch.Pitch('D3')})
        >>> p1.containsHiddenFifth(p2, 'Soprano', 'Bass')
        True
        '''
        cp = consequentPossibility
        hasHiddenFifth = False

        vlq = voiceLeading.VoiceLeadingQuartet(self[vlBottom], cp[vlBottom], self[vlTop], cp[vlTop])
        
        if vlq.hiddenFifth():
            if verbose:
                environRules = environment.Environment(_MOD)
                environRules.warn("Hidden fifths between " + vlTop + " and " + vlBottom + ".")
            hasHiddenFifth = True
            if not verbose:
                return hasHiddenFifth
            
        return hasHiddenFifth
    
    def containsHiddenOctave(self, consequentPossibility, vlTop, vlBottom, verbose = False):
        '''
        Checks for hidden octaves between self and a consequent possibility. To remove ambiguities,
        asked to provide the key of the top voice and the key of the bottom voice.
        
        >>> from music21 import *
        >>> from music21.figuredBass import possibility
        >>> p1 = possibility.Possibility({'Soprano': pitch.Pitch('A5'), 'Bass': pitch.Pitch('C3')})
        >>> p2 = possibility.Possibility({'Soprano': pitch.Pitch('D6'), 'Bass': pitch.Pitch('D3')})
        >>> p1.containsHiddenOctave(p2, 'Soprano', 'Bass')
        True
        '''
        cp = consequentPossibility
        hasHiddenOctave = False

        vlq = voiceLeading.VoiceLeadingQuartet(self[vlBottom], cp[vlBottom], self[vlTop], cp[vlTop])
                
        if vlq.hiddenOctave():
            if verbose:
                environRules = environment.Environment(_MOD)
                environRules.warn("Hidden octaves between " + vlTop + " and " + vlBottom + ".")
            hasHiddenOctave = True
            if not verbose:
                return hasHiddenOctave
            
        return hasHiddenOctave

    # TESSITURA RULES
    def containsVoiceOverlap(self, consequentPossibility, verbose = False):
        hasVoiceOverlap = False
        voiceQuartets = self._findVoiceQuartets(consequentPossibility)

        for (pitchA1, pitchA2, vl1, pitchB1, pitchB2, vl2) in voiceQuartets:
            vlq = voiceLeading.VoiceLeadingQuartet(pitchA1, pitchA2, pitchB1, pitchB2)
            if vlq.voiceOverlap():
                if verbose:
                    environRules = environment.Environment(_MOD)
                    environRules.warn("Voice overlap between " + vl1 + " and " + vl2 + ".")
                hasVoiceOverlap = True
                
        return hasVoiceOverlap

    # HELPER METHODS
    def _findVoicePairs(self, consequentPossibility):
        cp = consequentPossibility
        
        voicePairs = []
        for voiceLabel in cp.keys():
            voicePair = (self[voiceLabel], cp[voiceLabel], voiceLabel)
            voicePairs.append(voicePair)

        return voicePairs
    
    def _findVoiceQuartets(self, consequentPossibility):
        cp = consequentPossibility
        if len(cp.keys()) <= 1:
            raise PossibilityException("Not enough voices provided in consequent possibility.")
        for voiceLabel in cp.keys():
            if voiceLabel not in self.keys():
                raise PossibilityException("Key not shared among both self and consequent possibilities.")
            
        voicePairs = self._findVoicePairs(consequentPossibility)        
        voiceQuartets = []
        
        for i in range(len(voicePairs)):
            for j in range(i+1,len(voicePairs)):
                voiceQuartets.append(voicePairs[i] + voicePairs[j])
        
        return voiceQuartets
        

class PossibilityException(music21.Music21Exception):
    pass

#-------------------------------------------------------------------------------
class Test(unittest.TestCase):

    def runTest(self):
        pass

if __name__ == "__main__":
    music21.mainTest(Test)

#------------------------------------------------------------------------------
# eof