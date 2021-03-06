# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# Name:         sites.py
# Purpose:      Objects for keeping track of relationships among Music21Objects
#
# Authors:      Michael Scott Cuthbert
#               Christopher Ariza
#
# Copyright:    Copyright © 2007-2014 Michael Scott Cuthbert and the music21 Project
# License:      LGPL or BSD, see license.txt
#-------------------------------------------------------------------------------
'''
sites.py -- Objects for keeping track of relationships among Music21Objects
'''
import unittest

from music21 import common
from music21 import defaults
from music21 import exceptions21
from music21.ext import six

if six.PY3:
    basestring = str # @ReservedAssignment

# define whether weakrefs are used for storage of object locations
WEAKREF_ACTIVE = True

#DEBUG_CONTEXT = False

DENOM_LIMIT = defaults.limitOffsetDenominator


class SitesException(exceptions21.Music21Exception):
    pass


#------------------------------------------------------------------------------
class SiteRef(common.SlottedObject):
    '''
    a single Site (stream, container, parent, reference, etc.) stored inside the Sites object.

    A very simple object.
    
    This site would be stored in the .sites.siteDict for, say a note.Note, if it were in
    st at offset 20.0
    
    >>> st = stream.Stream()
    >>> st.id = 'hi'
    
    >>> s = sites.SiteRef()
    >>> s.classString = st.classes[0]
    >>> s.site = st
    >>> s.offset = 20.0
    >>> s.isDead
    False

    If you call s.site, you always get an object out, but internally, there's a .siteWeakref that
    stores a weakref to the site.

    >>> s.site
    <music21.stream.Stream hi>
    >>> s.siteWeakref
    <weakref at 0x...; to 'Stream' at 0x...>
    

    Ways of working with tuplets:
    
    >>> s.offset = 1/3.0
    >>> s.offset
    Fraction(1, 3)
    >>> s.offsetRational # same
    Fraction(1, 3)
    >>> s.offsetFloat
    0.333...

    
    OMIT_FROM_DOCS
    if you turn sites.WEAKREF_ACTIVE to False then .siteWeakref just stores another reference to
    the site.
    
    
    '''
    ### CLASS VARIABLES ###

    __slots__ = (
        'classString',
        'globalSiteIndex',
        'siteIndex',
        'isDead',
        'siteWeakref',
        '_offset',
        )
    ### INITIALIZER ###

    def __init__(self):
        self.isDead = False
    
    def _getAndUnwrapSite(self):
        # should set isDead?
        return common.unwrapWeakref(self.siteWeakref)
    
    def _setAndWrapSite(self, site):
        self.siteWeakref = common.wrapWeakref(site)

    site = property(_getAndUnwrapSite, _setAndWrapSite)


    def _getOffsetFloat(self):
        if isinstance(self._offset, basestring):
            return self._offset
        elif self._offset is not None:
            return float(self._offset)
        else:
            return None
    
    def _setOffset(self, offset):
        '''
        sets the offset and if necessary, translates it to a Fraction for exact representation.
        '''
        if offset is None:
            self._offset = None
        elif isinstance(offset, basestring):
            self._offset = offset
        else:
            self._offset = common.opFrac(offset)
    def _getOffsetRational(self):
        '''
        returns the offset without conversion to float...
        '''
        return self._offset
    
    offset = property(_getOffsetRational, _setOffset)
    offsetRational = property(_getOffsetRational, _setOffset)
    offsetFloat = property(_getOffsetFloat, _setOffset, doc='''synonym for offset''')


_singletonCounter = common.SingletonCounter()

class Sites(common.SlottedObject):
    '''
    An object, stored within a Music21Object, that stores (weak) references to
    a collection of objects that may be contextually relevant to this object.

    Some of these objects are locations (also called sites), or Streams that
    contain this object. In this case the Sites object stores an offset value,
    used for determining position within a Stream.

    All defined contexts are stored as dictionaries in a dictionary. The
    outermost dictionary stores objects.
    '''

    ### CLASS VARIABLES ###

    __slots__ = (
        'siteDict',
        '_lastID',
        '_lastOffset',
        '_locationKeys',
        '_siteIndex',
        'containedById',
        )
    
    ### INITIALIZER ###

    def __init__(self, containedById=None):
        # a dictionary of dictionaries
        self.siteDict = {}
        # store idKeys in lists for easy access
        # the same key may be both in locationKeys and contextKeys
        self._locationKeys = []

        # store an index of numbers for tagging the order of creation of defined contexts;
        # this is used to be able to discern the order of context as added
        self._siteIndex = 0
        
        # pass a reference to the object that contains this
        self.containedById = containedById
        # cache for performance
        self._lastID = -1  # cannot be None
        self._lastOffset = None

    ## SPECIAL METHODS ###

    def __deepcopy__(self, memo=None):
        '''
        Helper function for copy.deepcopy that in addition to copying produces
        a new, independent Sites object.  This does not, however, deepcopy site
        references stored therein.

        All sites, however, are passed on to the new deepcopy, which means that
        in a deepcopy of a Stream that contains Notes, the copied Note will
        have the former site as a location, even though the new Note instance
        is not actually found in the old Stream.

        ::

            >>> import copy
            >>> class Mock(base.Music21Object):
            ...     pass
            >>> aObj = Mock()
            >>> aContexts = sites.Sites()
            >>> aContexts.add(aObj)
            >>> bContexts = copy.deepcopy(aContexts)
            >>> len(aContexts.get()) == 1
            True

        ::

            >>> len(bContexts.get()) == 1
            True

        ::

            >>> aContexts.get() == bContexts.get()
            True

        '''
        #TODO: it may be a problem that sites are being transferred to deep
        #copies; this functionality is used at times in context searches, but
        # may be a performance hog.

        new = self.__class__()
        locations = []  # self._locationKeys[:]
        #environLocal.printDebug(['Sites.__deepcopy__', 'self.siteDict.keys()', self.siteDict.keys()])
        for idKey in self.siteDict:
            oldSite = self.siteDict[idKey]
            if oldSite.isDead:
                continue  # do not copy dead references
            newSite = SiteRef()
            newSite.site = oldSite.site
            if oldSite.site is None:
                newIdKey = None
            else:
                newIdKey = id(newSite.site)
                #if newIdKey != idKey and oldSite.site != None:
                #    print "WHOA! %s %s" % (newIdKey, idKey)
            # not copying the offset in deepcopying means that
            # the old site becomes a context, not a site
            # this is still experimental
            # post.offset = None
            newSite.offset = oldSite.offset
            if newSite.offset is not None:
                locations.append(newIdKey)  # if offset not None, a location

            newSite.siteIndex = oldSite.siteIndex
            newSite.globalSiteIndex = _singletonCounter()
            newSite.classString = oldSite.classString
            newSite.isDead = False
            ### debug
            #originalObj = post.site
            #if id(originalObj) != idKey and originalObj is not None:
            #    print idKey, id(originalObj)
            new.siteDict[newIdKey] = newSite

        new._locationKeys = locations
        new._siteIndex = self._siteIndex  # keep to stay coherent
        return new

    def __len__(self):
        '''
        Return the total number of references.

        ::

            >>> class Mock(base.Music21Object):
            ...     pass
            >>> aObj = Mock()
            >>> aContexts = sites.Sites()
            >>> aContexts.add(aObj)
            >>> len(aContexts)
            1

        '''
        return len(self.siteDict)

    ### PRIVATE METHODS ###

    def _keysByTime(self, newFirst=True):
        '''
        Get keys sorted by creation time, where most
        recent are first if `newFirst` is True. else, most recent are last.

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aObj = Mock()
            >>> bObj = Mock()
            >>> cObj = Mock()
            >>> aSites = music21.Sites()
            >>> aSites.add(cObj, 345)
            >>> aSites.add(aObj)
            >>> aSites.add(bObj)
            >>> k = aSites._keysByTime()
            >>> aSites.siteDict[k[0]].siteIndex > aSites.siteDict[k[1]].siteIndex > aSites.siteDict[k[2]].siteIndex
            True

        '''
        post = []
        for key in self.siteDict:
            post.append((self.siteDict[key].siteIndex, key))
        post.sort()
        if newFirst:
            post.reverse()
        return [k for unused_time, k in post]

    ### PUBLIC METHODS ###

    def add(self, obj, offset=None, timeValue=None, idKey=None, classString=None):
        '''
        Add a reference to the `Sites` collection for this object.

        N.B. -- like all .sites operations, this is an advanced tool not for
        standard music21 usage.  Instead of:

            elObj.add(streamObj, 20.0)

        use this command, which will take care of `.sites.add` as well as
        putting `elObj` in `streamObj.elements`:

            streamObj.insert(20.0, elObj)

        If `offset` is `None`, then `obj` is interpreted as a Context (such as
        a temperament, a time period, etc.)

        If `offset` is not `None`, then `obj` is interpreted as location, i.e.,
        a :class:`~music21.stream.Stream`.

        `offset` can also be the term `highestTime` which is the highest
        available time in the obj (used for ``streamObj.append(el)``)

        The `timeValue` argument is used to store the time as an int
        (in milliseconds after Jan 1, 1970) when this object was added to locations. 
        If set to `None`, then the current time is used.

        `idKey` stores the id() of the obj.  If `None`, then id(obj) is used.

        `classString` stores the class of obj.  If `None` then `obj.classes[0]`
        is used.

        TODO: Tests.  Including updates.
        '''
        # NOTE: this is a performance critical method

        # a None object will have a key of None
        # do not need to set this as is default
        if idKey is None and obj is not None:
            idKey = id(obj)

        updateNotAdd = False
        if idKey in self.siteDict:
            tempSiteRef = self.siteDict[idKey]
            if (tempSiteRef.isDead is False and
                tempSiteRef.site is not None):
                updateNotAdd = True

            #if idKey is not None:
            #    print "Updating idKey %s for object %s" % (idKey, id(obj))

        if offset is not None:  # a location, not a context
            if idKey not in self._locationKeys:
                self._locationKeys.append(idKey)
        #environLocal.printDebug(['adding obj', obj, idKey])
        # weak refs were being passed in __deepcopy__ calling this method
        # __deepcopy__ no longer call this method, so we can assume that
        # we will not get weakrefs

        if obj is not None:
            if classString is None:
                classString = obj.classes[0]  # get most current class

        if updateNotAdd is True:
            #if obj is not None and id(obj) != idKey:
            #    print("RED ALERT!")
            siteRef = self.siteDict[idKey]
            siteRef.isDead = False  # in case it used to be a dead site...            
        else:
            siteRef = SiteRef()
            #if id(obj) != idKey and obj is not None:
            #    print "Houston, we have a problem %r" % obj

        siteRef.site = obj  # stores a weakRef
        siteRef.offset = offset  # offset can be None for contexts
        siteRef.classString = classString
        # default
        # singleContextDict.isDead = False  # store to access w/o unwrapping
        # time is a numeric count, not a real time measure
        siteRef.siteIndex = self._siteIndex
        self._siteIndex += 1  # increment for next usage
        siteRef.globalSiteIndex = _singletonCounter() # increments
        ##
        if not updateNotAdd:  # add new/missing information to dictionary
            self.siteDict[idKey] = siteRef

    def clear(self):
        '''
        Clear all stored data.
        '''
        self.siteDict = {}
        self._locationKeys = []
        self._lastID = -1  # cannot be None
        self._lastOffset = None

    def get(self, locationsTrail=False, sortByCreationTime=False,
            priorityTarget=None, excludeNone=False):
        '''
        Get references; order, based on dictionary keys, is from most recently added to least recently added.

        The `locationsTrail` option forces locations to come after all other defined contexts.

        The `sortByCreationTime` option will sort objects by creation time,
        where most-recently assigned objects are returned first. Can be [False, other], [True, 1] or
        ['reverse', -1]

        If `priorityTarget` is defined, this object will be placed first in the list of objects.

        ::
        
            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aObj = Mock()
            >>> bObj = Mock()
            >>> cObj = Mock()
            >>> aSites = music21.Sites()
            >>> aSites.add(cObj, 345) # a locations
            >>> aSites.add(aObj)
            >>> aSites.add(bObj)
            >>> aSites.get() == [cObj, aObj, bObj]
            True

        ::

            >>> aSites.get(locationsTrail=True) == [aObj, bObj, cObj]
            True

        ::

            >>> aSites.get(sortByCreationTime=True) == [bObj, aObj, cObj]
            True

        '''
        if sortByCreationTime in [True, 1]:
            keyRepository = self._keysByTime(newFirst=True)
        # reverse creation time puts oldest elements first
        elif sortByCreationTime in [-1, 'reverse']:
            keyRepository = self._keysByTime(newFirst=False)
        else:  # None, or False
            keyRepository = self.siteDict

        post = []
        #purgeKeys = []

        # get partitioned list of all, w/ locations last if necessary
        if locationsTrail:
            keys = []
            keysLocations = []  # but possibly sorted
            for key in keyRepository:
                if key not in self._locationKeys:  # skip these
                    keys.append(key)  # others first
                else:
                    keysLocations.append(key)
            keys += keysLocations  # now locations are at end
        else:
            keys = keyRepository

        # get each dict from all defined contexts
        for key in keys:
            siteRef = self.siteDict[key]
            # check for None object; default location, not a weakref, keep
            if siteRef.siteWeakref is None:
                if not excludeNone:
                    post.append(siteRef.site)
            else:
                obj = siteRef.site
                if obj is None:  # dead ref
                    siteRef.isDead = True
                else:
                    post.append(obj)

        # remove dead references
#         if autoPurge:
#             for key in purgeKeys:
#                 self.removeById(key)

        if priorityTarget is not None:
            if priorityTarget in post:
                #environLocal.printDebug(['priorityTarget found in post:', priorityTarget])
                # extract object and make first
                post.insert(0, post.pop(post.index(priorityTarget)))
        return post

    def getAllByClass(self, className, found=None, idFound=None, memo=None):
        '''
        Return all known references of a given class found in any association
        with this Sites object.

        This will recursively search the defined contexts of existing defined
        contexts, and return a list of all objects that match the given class.

        >>> import music21
        >>> class Mock(music21.Music21Object):
        ...    pass
        ...
        >>> class Mocker(music21.Music21Object):
        ...    pass
        ...
        >>> aObj = Mock()
        >>> bObj = Mock()
        >>> cObj = Mocker()
        >>> dc = music21.Sites()
        >>> dc.add(aObj)
        >>> dc.add(bObj)
        >>> dc.add(cObj)
        >>> dc.getAllByClass(Mock) == [aObj, bObj]
        True

        A string (case insensitive) can also be used:
        
        >>> dc.getAllByClass("mock") == [aObj, bObj]
        True


        '''
        if memo is None:
            memo = {} # intialize
        if found is None:
            found = []
        if idFound is None:
            idFound = []

        objs = self.get(locationsTrail=False)
        for obj in objs:
            #environLocal.printDebug(['memo', memo])
            if obj is None:
                continue # in case the reference is dead
            if common.isStr(className):
                if type(obj).__name__.lower() == className.lower():
                    found.append(obj)
                    idFound.append(id(obj))
            elif isinstance(obj, className):
                    found.append(obj)
                    idFound.append(id(obj))
        for obj in objs:
            if obj is None:
                continue # in case the reference is dead
            # if after trying to match name, look in the defined contexts'
            # defined contexts [sic!]
            if id(obj) not in memo:
                # if the object is a Musci21Object
                #if hasattr(obj, 'getContextByClass'):
                # store this object as having been searched
                memo[id(obj)] = obj
                # will add values to found
                #environLocal.printDebug(['getAllByClass()', 'about to call getAllContextsByClass', 'found', found, 'obj', obj])
                obj.getAllContextsByClass(className, found=found,
                    idFound=idFound, memo=memo)
        # returning found, but not necessary
        return found

    def getAttrByName(self, attrName):
        '''
        Given an attribute name, search all objects and find the first that
        matches this attribute name; then return a reference to this attribute.

         >>> import music21
        >>> class Mock(music21.Music21Object):
        ...     attr1 = 234
        ...
        >>> aObj = Mock()
        >>> aObj.attr1 = 234
        >>> bObj = Mock()
        >>> bObj.attr1 = 98
        >>> aSites = music21.Sites()
        >>> aSites.add(aObj)
        >>> len(aSites)
        1

        >>> aSites.getAttrByName('attr1') == 234
        True

        >>> aSites.remove(aObj)
        >>> aSites.add(bObj)
        >>> aSites.getAttrByName('attr1') == 98
        True

        An incorrect attribute name will just give none:
        
        >>> aSites.getAttrByName('blah') is None
        True

        '''
        post = None
        for obj in self.get():
            if obj is None:
                continue # in case the reference is dead
            try:
                post = getattr(obj, attrName)
                return post
            except AttributeError:
                pass

    def getObjByClass(self, className, serialReverseSearch=True, callerFirst=None,
             sortByCreationTime=False, prioritizeActiveSite=False,
             priorityTarget=None, getElementMethod='getElementAtOrBefore',
             memo=None):
        '''
        Return the most recently added reference based on className.  Class
        name can be a string or the class name.

        This will recursively search the sitesDicts of objects in Site objects in 
        the siteDict.

        The `callerFirst` parameters is simply used to pass a reference of the
        first caller; this is necessary if we are looking within a Stream for a
        flat offset position.

        If `priorityTarget` is specified, this location will be searched first.
        The `prioritizeActiveSite` is pased to to any recursively called
        getContextByClass() calls.

        The `getElementMethod` is a string that selects which Stream method is
        used to get elements for searching with getElementsByClass() calls.

        >>> import music21
        >>> class Mock(music21.Music21Object):
        ...     pass
        ...
        >>> import time
        >>> aObj = Mock()
        >>> bObj = Mock()
        >>> aSites = music21.Sites()
        >>> aSites.add(aObj)
        >>> aSites.add(bObj)
        >>> # we get the most recently added object first
        >>> aSites.getObjByClass('Mock', sortByCreationTime=True) == bObj
        True
        
        >>> aSites.getObjByClass(Mock, sortByCreationTime=True) == bObj
        True

        OMIT_FROM_DOCS
        TODO: not sure if memo is properly working: need a test case
        '''
        #if DEBUG_CONTEXT: print 'Y: first call'
        # in general, this should not be the first caller, as this method
        # is called from a Music21Object, not directly on the Sites
        # instance. Nonetheless, if this is the first caller, it is the first
        # caller.
        if callerFirst is None:  # this is the first caller
            callerFirst = self  # set Sites as caller first
        if memo is None:
            memo = {}  # intialize
        post = None
        #count = 0

        # search any defined contexts first
        # need to sort: look at most-recently added objs are first
        objs = self.get(
            locationsTrail=False,
            sortByCreationTime=sortByCreationTime,
            priorityTarget=priorityTarget,
            excludeNone=True,
            )
        #printMemo(memo, 'getObjByClass() called: looking at %s sites' % len(objs))
        classNameIsStr = common.isStr(className)
        for obj in objs:
            #environLocal.printDebug(['memo', memo])
            if classNameIsStr:
                if className in obj.classes:
                    post = obj
                    break
            elif isinstance(obj, className):
                    post = obj
                    break
        if post is not None:
            return post

        # all objs here are containers, as they are all locations
        # if we could be sure that these objs do not have their own locations
        # and do not have the target class, we can skip
        for obj in objs:
            #if DEBUG_CONTEXT: print '\tY: getObjByClass: iterating objs:', id(obj), obj
            if (classNameIsStr and obj.isFlat):
                #if DEBUG_CONTEXT: print '\tY: skipping flat stream that does not contain object:', id(obj), obj
                #environLocal.printDebug(['\tY: skipping flat stream that does not contain object:'])
                if obj.sites.getSiteCount() == 0: # is top level; no more to search...
                    if not obj.hasElementOfClass(className, forceFlat=True):
                        continue # skip, not in this stream

            # if after trying to match name, look in the defined contexts'
            # defined contexts [sic!]
            #if post is None: # no match yet
            # access public method to recurse
            if id(obj) not in memo:
                # if the object is a Musci21Object
                #if hasattr(obj, 'getContextByClass'):
                # store this object as having been searched
                memo[id(obj)] = obj
                post = obj.getContextByClass(className,
                       serialReverseSearch=serialReverseSearch,
                       callerFirst=callerFirst,
                       sortByCreationTime=sortByCreationTime,
                       prioritizeActiveSite=prioritizeActiveSite,
                       getElementMethod=getElementMethod,
                       memo=memo)
                if post is not None:
                    break
#                 else: # this is not a music21 object
#                     pass
                    #environLocal.printDebug['cannot call getContextByClass on obj stored in DefinedContext:', obj]
#             else: # objec has already been searched
#                 pass
                #environLocal.printDebug['skipping searching of object already searched:', obj]
#             else: # post is not None
#                 break
        return post

    def getById(self, siteId):
        '''
        Return the object specified by an id.
        Used for testing and debugging.  Should NOT be used in production code.
        
        >>> a = note.Note()
        >>> s = stream.Stream()
        >>> s.append(a)
        >>> a.sites.getById(id(s)) is s
        True
        '''
        siteRef = self.siteDict[siteId]
        # need to check if these is weakref
        #if common.isWeakref(dict['obj']):
        return siteRef.site

    def getOffsetByObjectMatch(self, obj, returnType='rational'):
        '''
        For a given object, return the offset using a direct object match.  The
        stored id value is not used; instead, the id() of both the stored
        object reference and the supplied object is used.

        This should be replaced by getOffsetBySite(strictDeadCheck = True)...

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> aLocations = music21.Sites()
            >>> aLocations.add(aSite, 5)
            >>> aLocations.add(bSite, 3.2)
            >>> aLocations.getOffsetByObjectMatch(aSite)
            5.0
            >>> aLocations.getOffsetByObjectMatch(bSite)
            Fraction(16, 5)
            >>> aLocations.getOffsetByObjectMatch(bSite, returnType='float')
            3.2...

        '''
        for idKey in self.siteDict:
            siteRef = self.siteDict[idKey]
            if siteRef.isDead: # always skip
                continue
            # must unwrap references before comparison
            #if common.isWeakref(dict['obj']):
            compareObj = siteRef.site
            if compareObj is None: # mark isDead for later removal
                siteRef.isDead = True
                continue
            if id(compareObj) == id(obj):
                #environLocal.printDebug(['found object as site', obj, id(obj), 'idKey', idKey])
                return self.getOffsetBySiteId(idKey, returnType=returnType) #dict['offset']
        raise SitesException('an entry for this object (%s) is not stored in Sites' % obj)

    def getOffsetBySite(self, siteObj, returnType='rational'):
        '''
        For a given site return this Sites's offset in it. The None site is
        permitted. The id() of the site is used to find the offset.

        >>> import music21
        >>> class Mock(music21.Music21Object):
        ...     pass
        ...
        >>> aSite = Mock()
        >>> bSite = Mock()
        >>> aLocations = music21.Sites()
        >>> aLocations.add(aSite, 23)
        >>> aLocations.add(bSite, 121.5)
        >>> aLocations.getOffsetBySite(aSite)
        23.0

        >>> aLocations.getOffsetBySite(bSite)
        121.5


        The object might not actually be in the _elements for the site object, because
        it may be a deep copy, etc. but the number is still returned.
        '''
        # NOTE: this is a performance critical operation
        siteId = None
        if siteObj is not None:
            siteId = id(siteObj)
        try:
            # will raise a key error if not found
            return self.getOffsetBySiteId(siteId, returnType=returnType)
            #post = self.siteDict[siteId]['offset']
        except SitesException: # the site id is not valid
            #environLocal.printDebug(['getOffsetBySite: trying to get an offset by a site failed; self:', self, 'site:', site, 'defined contexts:', self.siteDict])
            raise # re-raise Exception

    def getOffsetBySiteId(self, idKey, strictDeadCheck=False, returnType='rational'):
        '''
        Main method for getting an offset from a location key.

        >>> import music21
        >>> class Mock(music21.Music21Object):
        ...     pass
        ...
        >>> aSite = Mock()
        >>> bSite = Mock()
        >>> cSite = Mock()
        >>> dSite = Mock()
        >>> eSite = Mock()
        >>> sitesObj = music21.Sites()
        >>> sitesObj.add(aSite, 0)
        >>> sitesObj.add(cSite) # a context
        >>> sitesObj.add(bSite, 234) # can add at same offset or a different one
        >>> sitesObj.add(dSite) # a context
        >>> sitesObj.getOffsetBySiteId(id(bSite))
        234.0

        If strictDeadCheck is False (default) we can still retrieve the context
        from a dead weakref.  This is necessary to get the offset from an
        iterated Stream often.  Eventually, this should become True -- but too
        many errors for now.

        >>> idBSite = id(bSite)
        >>> del(bSite)
        >>> sitesObj.siteDict[idBSite].siteWeakref
        <weakref at 0x...; dead>

        >>> sitesObj.siteDict[idBSite].siteWeakref is None
        False

        >>> sitesObj.siteDict[idBSite].site is None
        True

        >>> sitesObj.getOffsetBySiteId(idBSite, strictDeadCheck = False) # default
        234.0

        With this, you'll get an exception:

        >>> sitesObj.getOffsetBySiteId(idBSite, strictDeadCheck = True)
        Traceback (most recent call last):
        SitesException: Could not find the object with id ... in the Site marked with idKey ... (was there, now site is dead).
        object <music21.sites.Sites object at 0x...>, sitesDict: {...}
        containedById = ...

        '''
        # NOTE: this is a core method called very frequently
#        if idKey == self._lastID:
#            return self._lastOffset
        try:
            if returnType == 'float':
                value = self.siteDict[idKey].offsetFloat
            else:
                value = self.siteDict[idKey].offset
            
            if WEAKREF_ACTIVE and strictDeadCheck is True and self.siteDict[idKey].siteWeakref is not None:
                obj = self.siteDict[idKey].site
                if obj is None:
                    #if self.siteDict[idKey]['isDead'] is True: # not good enough
                    errorMsg = "Could not find the object with id %s in the Site marked with idKey %s (was there, now site is dead). " % (id(self), idKey)
                    errorMsg += "\n   object %r, sitesDict: %r" % (self, self.siteDict)
                    errorMsg += "\n   containedById = %r" % (self.containedById)
                    raise SitesException(errorMsg)

        except KeyError:
            errorMsg = "Could not find the object with id %s in the Site marked with idKey %s. " % (id(self), idKey)
            errorMsg += "\n   object %r, sitesDict: %r" % (self, self.siteDict)
            errorMsg += "\n   containedById = %d" % (self.containedById)
            raise SitesException(errorMsg)
        # stored string are assumed to be attributes of the stored object
        if isinstance(value, str):
            if value not in ['highestTime', 'lowestOffset', 'highestOffset']:
                raise SitesException('attempted to set a bound offset with a string attribute that is not supported: %s' % value)
            obj = self.siteDict[idKey].site
            # offset value is an attribute string
            # cannot cache these values as may change outside of siteDict
            return getattr(obj, value)
        # if value is not a string, it is a numerical offset
        self._lastID = idKey
        self._lastOffset = value
        return value

    def getOffsets(self, returnType='rational'):
        '''
        Return a list of all offsets.

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> cSite = Mock()
            >>> dSite = Mock()
            >>> sitesObj = music21.Sites()
            >>> sitesObj.add(aSite, 0)
            >>> sitesObj.add(cSite) # a context -- no offset
            >>> sitesObj.add(bSite, 2.33333333333) # can add at same offset or another
            >>> sitesObj.add(dSite) # a context -- no offset
            >>> sitesObj.getOffsets()
            [0.0, Fraction(7, 3)]
            
            Can call returnType = 'float' instead:
            
            >>> sitesObj.getOffsets(returnType='float')
            [0.0, 2.3333...]
        '''
        # here, already having location keys may be an advantage
        return [self.getOffsetBySiteId(x, returnType=returnType) for x in self._locationKeys]

    def getSiteByOffset(self, offset):
        '''
        For a given offset return the site that fits it

        More than one Site may have the same offset; this at one point returned
        the last site added by sorting time, but now we use a dict, so there's
        no guarantee that the one you want will be there -- need orderedDicts!

        ::

            >>> import fractions
            >>> class Mock(base.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> cSite = Mock()
            >>> sitesObj = sites.Sites()
            >>> sitesObj.add(aSite, 2)
            >>> sitesObj.add(bSite, 10.0/3)
            >>> aSite is sitesObj.getSiteByOffset(2)
            True
            >>> bSite is sitesObj.getSiteByOffset(fractions.Fraction(10, 3))
            True
            >>> bSite is sitesObj.getSiteByOffset(3.33333333333)
            True

        '''
        match = None
        offset = common.opFrac(offset)
        for siteId in self.siteDict:
            # might need to use almost equals here
            matched = False
            if self.siteDict[siteId].offsetRational == offset:
                matched = True
            if matched is True:
                if self.siteDict[siteId].isDead:
                    return None
                match = self.siteDict[siteId].site
                break
        return match

    def getSiteCount(self):
        '''
        Return the number of non-dead sites, excluding the None site.  This does not
        unwrap weakrefs for performance.
        
        >>> a = note.Note()
        >>> a.sites.getSiteCount()
        0
        >>> s = stream.Stream()
        >>> s.append(a)
        >>> a.sites.getSiteCount()
        1
        >>> sf = s.flat
        >>> a.sites.getSiteCount()
        2
        '''
        count = 0
        for idKey in self._locationKeys:
            siteRef = self.siteDict[idKey]
            if siteRef.isDead is True:
                continue
            if siteRef.siteWeakref is None:
                continue
            count += 1
        return count

    def getSiteIds(self):
        '''
        Return a list of all site Ids.

        >>> import music21
        >>> class Mock(music21.Music21Object):
        ...     pass
        ...
        >>> aSite = Mock()
        >>> bSite = Mock()
        >>> dc = music21.Sites()
        >>> dc.add(aSite, 0)
        >>> dc.add(bSite) # a context
        >>> dc.getSiteIds() == [id(aSite)]
        True
        '''
        # may want to convert to tuple to avoid user editing?
        return self._locationKeys

    def getSites(self, idExclude=None, excludeNone=False):
        '''
        Get all Site objects in .siteDict that are locations. 
        Note that this unwraps all sites from weakrefs and is thus an expensive operation.

        >>> import music21
        >>> class Mock(music21.Music21Object):
        ...     pass
        ...
        >>> aObj = Mock()
        >>> bObj = Mock()
        >>> aSites = music21.Sites()
        >>> aSites.add(aObj, 234)
        >>> aSites.add(bObj, 3000)
        >>> len(aSites.getSites())
        2
        >>> len(aSites.getSites(idExclude=[id(aObj)]))
        1
        '''
#         if idExclude is None:
#             idExclude = [] # else, assume a list
        # use pre-collected keys
        post = []
        for idKey in self._locationKeys:
            if idExclude is not None:
                if idKey in idExclude:
                    continue
            try:
                objRef = self.siteDict[idKey].site
            except KeyError:
                raise SitesException('no such site: %s' % idKey)
            # skip dead references
            if self.siteDict[idKey].isDead:
                continue
            if idKey is None:
                if not excludeNone:
                    post.append(None) # keep None as site
            elif not WEAKREF_ACTIVE: # leave None alone
                post.append(objRef)
            else:
                obj = common.unwrapWeakref(objRef)
                if obj is None:
                    self.siteDict[idKey].isDead = True
                    continue
                post.append(obj)
        return post

    def getSitesByClass(self, className):
        '''
        Return a list of unwrapped site from siteDict.site [SiteRef.site] (generally a Stream) 
        that matches the provided class.

        Input can be either a Class object or a string

            >>> import music21
            >>> from music21 import stream
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aObj = Mock()
            >>> bObj = Mock()
            >>> cObj = stream.Stream()
            >>> aSites = music21.Sites()
            >>> aSites.add(aObj, 234)
            >>> aSites.add(bObj, 3000)
            >>> aSites.add(cObj, 200)
            >>> aSites.getSitesByClass(Mock) == [aObj, bObj]
            True

        ::

            >>> aSites.getSitesByClass('Stream') == [cObj]
            True

        '''
        found = []
        if not isinstance(className, str):
            className = common.classToClassStr(className)

        for idKey in self._locationKeys:
            siteRef = self.siteDict[idKey]
            if siteRef.isDead:
                continue
            classStr = siteRef.classString
            if classStr == className:
                objRef = siteRef.site
                if not WEAKREF_ACTIVE: # leave None alone
                    obj = objRef
                else:
                    obj = common.unwrapWeakref(objRef)
                found.append(obj)
        return found

    def hasSiteId(self, siteId):
        '''
        Return True or False if this Sites object already has this site id
        defined as a location

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> dc = music21.Sites()
            >>> dc.add(aSite, 0)
            >>> dc.add(bSite) # a context
            >>> dc.hasSiteId(id(aSite))
            True

        ::

            >>> dc.hasSiteId(id(bSite))
            False

        '''
        if siteId in self._locationKeys:
            return True
        return False

    def hasSpannerSite(self):
        '''
        Return True if this object is found in any Spanner. This is determined
        by looking for a SpannerStorage Stream class as a Site.
        '''
        for idKey in self._locationKeys:
            if self.siteDict[idKey].isDead:
                continue
            if self.siteDict[idKey].classString == 'SpannerStorage':
                return True
        return False

    def hasVariantSite(self):
        '''
        Return True if this object is found in any Variant. This is determined
        by looking for a VariantStorage Stream class as a Site.
        '''
        for idKey in self._locationKeys:
            if self.siteDict[idKey].isDead:
                continue
            if self.siteDict[idKey].classString == 'VariantStorage':
                return True
        return False

    def isSite(self, obj):
        '''
        Given an object, determine if it is an object in a Site stored in this 
        Sites's siteDict. This
        will return False if the object is simply a context and not a location.

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> aLocations = music21.Sites()
            >>> aLocations.add(aSite, 0)
            >>> aLocations.add(bSite) # a context
            >>> aLocations.isSite(aSite)
            True

        ::

            >>> aLocations.isSite(bSite)
            False

        '''
        if id(obj) in self._locationKeys:
            return True
        return False

    def purgeLocations(self, rescanIsDead=False):
        '''
        Clean all locations that refer to objects that no longer exist.

        The `removeOrphanedSites` option removes sites that may have been the
        result of deepcopy: the element has the site, but the site does not
        have the element. This results b/c Sites are shallow-copied, and then
        elements are re-added.

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> cSite = Mock()
            >>> dSite = Mock()
            >>> aLocations = music21.Sites()
            >>> aLocations.add(aSite, 0)
            >>> aLocations.add(cSite) # a context
            >>> del aSite
            >>> len(aLocations)
            2

        ::

            >>> aLocations.purgeLocations(rescanIsDead=True)
            >>> len(aLocations)
            1

        '''
        # first, check if any sites are dead, and cache the results
        if rescanIsDead:
            for idKey in self._locationKeys:
                if idKey is None:
                    continue
                siteRef = self.siteDict[idKey]
                #if siteRef.isDead:
                #    continue  # already marked -- do it again, in case it is reused
                if WEAKREF_ACTIVE:
                    obj = common.unwrapWeakref(
                        siteRef.site)
                else:
                    obj = siteRef.site
                if obj is None: # if None, it no longer exists
                    siteRef.isDead = True
                else:
                    siteRef.isDead = False
        # use previously set isDead entry, so as not to
        # unwrap all references
        remove = []
        for idKey in self._locationKeys:
            if idKey is None:
                continue
            siteRef = self.siteDict[idKey]
            if siteRef.isDead:
                remove.append(idKey)
                
        for idKey in remove:
            # this call changes the ._locationKeys list, and thus must be
            # out side _locationKeys loop
            self.removeById(idKey)

    def remove(self, site):
        '''
        Remove the object (a context or location site) specified from Sites.
        Object provided can be a location site (i.e., a Stream) or a pure
        context (like a Temperament).

        N.B. -- like all .sites operations, this is an advanced tool not for
        standard music21 usage.  Instead of:

            elObj.remove(streamObj)

        use this command, which will take care of `.sites.remove` as well as
        removing `elObj` from `streamObj.elements`:

            streamObj.remove(elObj)

        ::

            >>> class Mock(base.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> cSite = Mock()
            >>> aSites = sites.Sites()
            >>> aSites.add(aSite, 23)
            >>> len(aSites)
            1

        ::

            >>> aSites.add(bSite, 233)
            >>> len(aSites)
            2

        ::

            >>> aSites.add(cSite, 232223)
            >>> len(aSites)
            3

        ::

            >>> aSites.remove(aSite)
            >>> len(aSites)
            2

        OMIT_FROM_DOCS

        ::

            >>> len(aSites._locationKeys)
            2

        '''
        # must clear
        self._lastID = -1  # cannot be None
        self._lastOffset = None

        siteId = None
        if site is not None:
            siteId = id(site)
        try:
            del self.siteDict[siteId]
            #environLocal.printDebug(['removed site w/o exception:', siteId, 'self.siteDict.keys()', self.siteDict.keys()])
        except:
            raise SitesException('an entry for this object (%s) is not stored in this Sites object' % site)
        # also delete from location keys
        if siteId in self._locationKeys:
            self._locationKeys.pop(self._locationKeys.index(siteId))

    def removeById(self, idKey):
        '''
        Remove a site entry by id key,
        which is id() of the object.
        '''
        # must clear if removing
        if idKey == self._lastID:
            self._lastID = -1  # cannot be None
            self._lastOffset = None
        if idKey is None:
            raise SitesException('trying to remove None idKey is not allowed')

        #environLocal.printDebug(['removeById', idKey, 'self.siteDict.keys()', self.siteDict.keys()])
        try:
            del self.siteDict[idKey]
        except KeyError:
            pass # could already be gone...
        if idKey in self._locationKeys:
            self._locationKeys.pop(self._locationKeys.index(idKey))

    def setAttrByName(self, attrName, value):
        '''
        Given an attribute name, search all objects and find the first that
        matches this attribute name; then return a reference to this attribute.

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     attr1 = 234
            ...
            >>> aObj = Mock()
            >>> bObj = Mock()
            >>> bObj.attr1 = 98
            >>> aSites = music21.Sites()
            >>> aSites.add(aObj)
            >>> aSites.add(bObj)
            >>> aSites.setAttrByName('attr1', 'test')
            >>> aSites.getAttrByName('attr1') == 'test'
            True

        '''
        #post = None
        for obj in self.get():
            if obj is None:
                continue  # in case the reference is dead
            try:
                junk = getattr(obj, attrName)  # if attr already exists
                setattr(obj, attrName, value)  # if attr already exists
            except AttributeError:
                pass

    def setOffsetBySite(self, site, value):
        '''Changes the offset of the site specified.  Note that this can also
        be done with add, but the difference is that if the site is not in
        Sites, it will raise an exception.

        ::

            >>> import music21
            >>> class Mock(music21.Music21Object):
            ...     pass
            ...
            >>> aSite = Mock()
            >>> bSite = Mock()
            >>> cSite = Mock()
            >>> aLocations = music21.Sites()
            >>> aLocations.add(aSite, 23)
            >>> aLocations.add(bSite, 121.5)
            >>> aLocations.setOffsetBySite(aSite, 20)
            >>> aLocations.getOffsetBySite(aSite)
            20.0

        ::

            >>> aLocations.setOffsetBySite(cSite, 30)
            Traceback (most recent call last):
            SitesException: an entry for this object (<...Mock object at 0x...>) is not stored in Sites

        '''
        siteId = None
        if site is not None:
            siteId = id(site)
        # will raise an index error if the siteId does not exist
        try:
            self.siteDict[siteId].offset = value
            self._lastID = siteId
            self._lastOffset = value
        except KeyError:
            raise SitesException('an entry for this object (%s) is not stored in Sites' % site)

    def setOffsetBySiteId(self, siteId, value):
        '''
        Set an offset by siteId. This assumes that the site is valid, is best
        used for advanced, performance critical usage only.

        The `siteId` parameter can be None.
        '''
        try:
            self.siteDict[siteId].offset = value
            self._lastID = siteId
            self._lastOffset = value
        except KeyError:
            raise SitesException('an entry for this object (%s) is not stored in Sites' % siteId)


class Test(unittest.TestCase):
    def testSites(self):
        from music21 import note, stream, corpus, clef

        m = stream.Measure()
        m.number = 34
        n = note.Note()
        m.append(n)

        n2 = note.Note()
        n2.sites.add(m)
        
        c = clef.Clef()
        c.sites.add(n)
        
        self.assertEqual(n2.getContextAttr('number'), 34)
        c.setContextAttr('lyric',
                               n2.getContextAttr('number'))
        # converted to a string now
        self.assertEqual(n.lyric, '34')


        violin1 = corpus.parse(
            "beethoven/opus18no1",
            3,
            fileExtensions='xml',
            ).getElementById("Violin I")
        lastNote = violin1.flat.notes[-1]
        lastNoteClef = lastNote.getContextByClass(clef.Clef)
        self.assertEqual(isinstance(lastNoteClef, clef.TrebleClef), True)


#-----------------------------------------------------------------------------
_DOC_ORDER = [SiteRef, Sites]


#------------------------------------------------------------------------------
if __name__ == "__main__":
    import music21
    music21.mainTest(Test)
