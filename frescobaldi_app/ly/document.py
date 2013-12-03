# This file is part of the Frescobaldi project, http://www.frescobaldi.org/
#
# Copyright (c) 2013 - 2013 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.

"""
DocumentBase and Document
=========================

Represents a lilypond source document (the text contents).

The Document implementation keeps the document in a (unicode) text string, 
but you can inherit from the DocumentBase class to support other 
representations of the text content.

Modifying is done inside a context (the with statement), e.g.:

d = Document('some string')
with d:
    d[5:5] = 'different '
d.plaintext()  --> 'some different string'

Changes are applied when the context is exited, also the modified part of the
document is re-tokenized. Changes may not overlap.

The tokens(block) method returns a tuple of tokens for the specified block. 
Depending on the implementation, a block describes a line in the LilyPond 
source document. It is not expected to have any methods, except that the 
'==' operator is supported between two blocks, and returns True if both 
refer to the same line of text in the source document.


Runner
======

A Runner allows iterating back and forth over the tokens of a document.



"""

from __future__ import unicode_literals
from __future__ import absolute_import

import sys
import operator
import collections


class DocumentBase(object):
    """Abstract base class for Document instances.
    
    You should inherit the following methods:
    
    setplaintext
    __len__
    __getitem__
    block
    index
    position
    text
    tokens
    isvalid
    initial_state
    state_end
    apply_changes
    
    You may inherit (e.g. to get speed improvements):
    
    plaintext
    next_block
    previous_block
    blocks_forward
    blocks_backward
    state
    
    """
    
    def __init__(self):
        """Constructor"""
        self._writing = 0
        self._changes = collections.defaultdict(list)
    
    def __nonzero__(self):
        return True
    
    def __len__(self):
        """Return the number of blocks"""
        raise NotImplementedError()
    
    def __getitem__(self, index):
        """Return the block at the specified index."""
        raise NotImplementedError()
        
    def plaintext(self):
        """The document contents as a plain text string."""
        return '\n'.join(map(self.text, self))

    def setplaintext(self, text):
        """Sets the document contents to the text string."""
        raise NotImplementedError()

    def size(self):
        """Return the number of characters in the document."""
        last_block = self[len(self) - 1]
        return self.position(last_block) + len(self.text(last_block))

    def block(self, position):
        """Return the text block at the specified character position.
        
        The text block itself has no methods, but it can be used as an
        argument to other methods of this class.
        
        (Blocks do have to support the '==' operator.)
        
        """
        raise NotImplementedError()
    
    def index(self, block):
        """Return the linenumber of the block (starting with 0)."""
        raise NotImplementedError()
         
    def blocks_forward(self, block):
        """Iter forward starting with the specified block."""
        while self.isvalid(block):
            yield block
            block = self.next_block(block)

    def blocks_backward(self, block):
        """Iter backwards starting with the specified block."""
        while self.isvalid(block):
            yield block
            block = self.previous_block(block)

    def position(self, block):
        """Return the position of the specified block."""
        raise NotImplementedError()

    def text(self, block):
        """Return the text of the specified block."""
        raise NotImplementedError()
    
    def next_block(self, block):
        """Return the next block, which may be invalid."""
        index = self.index(block)
        if index < len(self) - 1:
            return self[index + 1]
    
    def previous_block(self, block):
        """Return the previous block, which may be invalid."""
        index = self.index(block)
        if index > 0:
            return self[index - 1]
    
    def isvalid(self, block):
        """Return True if the block is a valid block."""
        raise NotImplementedError()
    
    def isblank(self, block):
        """Return True if the block is empty or blank."""
        t = self.text(block)
        return not t or t.isspace()

    def __enter__(self):
        """Start the context for modifying the document."""
        self._writing += 1
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context for modifying."""
        if exc_type is not None:
            # cancel all edits when an exception occurred
            self._writing = 0
            self._changes.clear()
        elif self._writing == 1:
            if self._changes:
                self.apply_changes()
            self._writing = 0
            self._changes.clear()
        elif self._writing > 1:
            self._writing -= 1
    
    def check_changes(self):
        """Debugging method that checks for overlapping edits."""
        end = self.size()
        changes = sorted(self._changes.items(), reverse=True)
        for start, items in changes:
            for pos, text in items:
                if pos > end:
                    if len(text) > 12:
                        text = text[:10] + '...'
                    raise ValueError("overlapping edit: {0}-{1}: {2}".format(start, pos, text))
            end = start

    def apply_changes(self):
        """Apply the changes and update the tokens."""
        raise NotImplementedError()
        
    def tokens(self, block):
        """Return the tuple of tokens of the specified block."""
        raise NotImplementedError()
    
    def initial_state(self):
        """Return the state at the beginning of the document."""
        raise NotImplementedError()
        
    def state(self, block):
        """Return the state at the start of the specified block."""
        prev = self.previous_block(block)
        if self.isvalid(prev):
            return self.state_end(prev)
        return self.initial_state()
            
    def state_end(self, block):
        """Return the state at the end of the specified block."""
        raise NotImplementedError()
    
    def slice(self, block, token, start=0, end=None):
        """Return a slice describing the position of the token in the text.
        
        If start is given the slice will start at position start in the token
        (from the beginning of the token). Start defaults to 0.
        If end is given, the cursor will end at that position in the token (from
        the beginning of the token). End defaults to the length of the token.
       
        """
        pos = self.position(block) + token.pos
        start = pos + start
        end = pos + (len(token) if end is None else end)
        return slice(start, end)
    
    ##
    # text modifying methods
    ##
    
    def append(self, text):
        """Append text to the end of the document."""
        end = self.size()
        self[end:end] = text
    
    def insert(self, pos, text):
        """Insert text at position."""
        self[pos:pos] = text
    
    def remove(self, s):
        """Remove text at slice."""
        del self[s]
    
    def replace(self, s, text):
        """Replace text at slice."""
        self[s] = text
    
    def __setitem__(self, key, text):
        """Change the text pointed to in key (integer or slice).
        
        If start > stop in the slice (and stop is not None), start and stop
        are swapped. (This is different than usual Python behaviour, where
        stop is set to start if it was lower.)
        
        """
        if isinstance(key, slice):
            start = key.start or 0
            end = key.stop
            if end is not None and start > end:
                start, end = end, start
        else:
            start = key
            end = start + 1
        self._changes[start].append((end, text.replace('\r', '')))

    def __delitem__(self, key):
        """Remove the range of text."""
        self[key] = ""


class Document(DocumentBase):
    """A plain text LilyPond source document
    
    that auto-updates the tokens.
    
    """
    def __init__(self, text=''):
        super(Document, self).__init__()
        self.setplaintext(text)
    
    def __len__(self):
        """Return the number of blocks"""
        return len(self._blocks)
    
    def __getitem__(self, index):
        """Return the block at the specified index."""
        return self._blocks[index]
        
    def setplaintext(self, text):
        lines = text.replace('\r', '').split('\n')
        self._blocks = [Block(t, n) for n, t in enumerate(lines)]
        pos = 0
        for b in self._blocks:
            b.position = pos
            pos += len(b.text) + 1
        
        # TODO update all tokens
        
    def block(self, position):
        """Return the text block at the specified character position."""
        if 0 <= position <= self._blocks[-1].position + len(self._blocks[-1].text):
            lo = 0
            hi = len(self._blocks)
            while lo < hi:
                mid = (lo + hi) // 2
                if position < self._blocks[mid].position:
                    hi = mid
                else:
                    lo = mid + 1
            return self._blocks[lo-1]
     
    def index(self, block):
        """Return the linenumber of the block (starting with 0)."""
        return block.index

    def position(self, block):
        """Return the position of the specified block."""
        return block.position

    def text(self, block):
        """Return the text of the specified block."""
        return block.text
    
    def isvalid(self, block):
        """Return True if the block is a valid block."""
        return bool(block)
    
    def tokens(self, block):
        """Return the tuple of tokens of the specified block."""
        return block.tokens
    
    def apply_changes(self):
        changes = sorted(self._changes.items(), reverse=True)
        for start, items in changes:
            s = self.block(start)
            for end, text in items:
                # first remove the old contents
                if end is None:
                    # all text to the end should be removed
                    s.text = s.text[:start - s.position]
                    del self._blocks[s.index+1:]
                else:
                    # remove til end position
                    e = self.block(end)
                    s.text = s.text[:start - s.position] + e.text[end - e.position:]
                    del self._blocks[s.index+1:e.index+1]
                # now insert the new stuff
                if text:
                    lines = text.split('\n')
                    lines[-1] += s.text[start - s.position:]
                    s.text = s.text[:start - s.position] + lines[0]
                    self._blocks[s.index+1:s.index+1] = map(Block, lines[1:])
                
        # update the position of all the new blocks
        pos = s.position
        for i, b in enumerate(self._blocks[s.index:], s.index):
            b.index = i
            b.position = pos
            pos += len(b.text) + 1
        
        # TODO update the tokens from block s



class Block(object):
    """A line of text.
    
    This class is only used by the Document implementation.
    
    """
    
    position = sys.maxint  # prevent picking those blocks before updating pos
    state    = None
    tokens   = None
    
    def __init__(self, text="", index=-1):
        self.text = text
        self.index = index


class TokenCursor(object):
    """Iterates back and forth over tokens.
    
    A TokenCursor can stop anywhere and remembers its current token.
    
    """
    def __init__(self, doc):
        self._doc = doc
    
    def document(self):
        """Return our Document."""
        return self._doc
    
    def move_to_position(self, position):
        """Positions the TokenCursor at the specified position."""
        block = self._doc.block(position)
        self.move_to_block(block)
        for t in self.forward_line():
            if self.position() + len(t) > position:
                if self.position() == position:
                    self._index -= 1
                break
        
    def move_to_block(self, block, at_end=False):
        """Positions the TokenCursor at the start of the given QTextBlock.
        
        If at_end == True, the iterator is positioned past the end of the block.
        
        """
        self.block = block
        self._tokens = self._doc.tokens(block)
        self._index = len(self._tokens) if at_end else -1
    
    def valid(self):
        """Return whether the current block is valid."""
        return self._doc.isvalid(self.block)
    
    def forward_line(self):
        """Yields tokens in forward direction in the current block."""
        while self._index + 1 < len(self._tokens):
            self._index += 1
            yield self._tokens[self._index]
    
    def forward(self):
        """Yields tokens in forward direction across blocks."""
        while self.valid():
            for t in self.forward_line():
                yield t
            self.next_block()
    
    def backward_line(self):
        """Yields tokens in backward direction in the current block."""
        while self._index > 0:
            self._index -= 1
            yield self._tokens[self._index]
    
    def backward(self):
        """Yields tokens in backward direction across blocks."""
        while self.valid():
            for t in self.backward_line():
                yield t
            self.previous_block()
    
    def at_block_start(self):
        """Returns True if the iterator is at the start of the current block."""
        return self._index <= 0
    
    def at_block_end(self):
        """Returns True if the iterator is at the end of the current block."""
        return self._index >= len(self._tokens) - 1
        
    def previous_block(self, at_end=True):
        """Go to the previous block, positioning the cursor at the end by default.
        
        Returns False if there was no previous block, else True.
        
        """
        valid = self.valid()
        if valid:
            self.move_to_block(self._doc.previous_block(self.block), at_end)
        return valid
    
    def next_block(self, at_end=False):
        """Go to the next block, positioning the cursor at the start by default.
        
        Returns False if there was no next block, else True.
        
        """
        valid = self.block.isValid()
        if valid:
            self.move_to_block(self._doc.next_block(self.block), at_end)
        return valid
    
    def token(self):
        """Re-returns the last yielded token."""
        return self._tokens[self._index]
        
    def position(self):
        """Returns the position of the current token."""
        return self._doc.position(self.block) + self._tokens[self._index].pos
    
    def slice(self, start=0, end=None):
        """Returns a slice for the last token.
        
        If start is given the slice will start at position start in the token
        (from the beginning of the token). Start defaults to 0.
        If end is given, the slice will end at that position in the token (from
        the beginning of the token). End defaults to the length of the token.
        
        """
        return self._doc.slice(self.block, self._tokens[self._index], start, end)

    def copy(self):
        """Return a new TokenCursor at the current position."""
        obj = type(self)(self._doc)
        obj.block = self.block
        obj._tokens = self._tokens
        obj._index = self._index
        return obj


OUTSIDE = -1
PARTIAL = 0
INSIDE  = 1


class TokenIterator(object):
    """Helper iterator.
    
    Iterates over the (block, tokens) tuples from a Document (or a part 
    thereof). Stores the current block in the block attribute and the tokens 
    (which also is a generator) in the tokens attribute.
    
    Iterating over the source object itself just yields the tokens, while the
    block attribute contains the current block.
    
    You can also iterate over the tokens attribute, which will yield the
    remaining tokens of the current block and then stop.
    
    If you specify a state, the tokens will update the state. If you specify
    state = True, the state will be taken from the document.
    
    """
    
    def __init__(self, document, state=None, start=0, end=None, partial=INSIDE):
        """Initialize the iterator.
        
        The document is a ly.document.DocumentBase instance.
        start is the starting position (defaulting to 0).
        end is the ending position (defaulting to None, the document end).
        partial is either self.OUTSIDE, PARTIAL, or INSIDE:
            OUTSIDE: tokens that touch the selected range are also yielded
            PARTIAL: tokens that overlap the start or end positions are yielded
            INSIDE:  (default) yield only tokens fully contained in the range
        The partial argument only makes sense if start or end are specified. 
        
        """
        self._doc = document
        start_block = document.block(start)
        
        # start, end predicates
        _predicates = {
            OUTSIDE: (
                lambda t: t.end < start_pos,
                lambda t: t.pos > end_pos,
            ),
            PARTIAL: (
                lambda t: t.end <= start_pos,
                lambda t: t.pos >= end_pos,
            ),
            INSIDE: (
                lambda t: t.pos < start_pos,
                lambda t: t.end > end_pos,
            ),
        }
        start_pred, end_pred = _predicates[partial]
        
        # if a state is given, use it (True: pick state from doc)
        if state:
            if state is True:
                state = document.state(start_block)
            def token_source(block):
                for t in document.tokens(block):
                    state.follow(t)
                    yield t
        else:
            def token_source(block):
                return iter(document.tokens(block))
        self.state = state
        
        # where to start
        if start:
            start_pos = start - document.position(start_block)
            # token source for first block
            def source_start(block):
                source = token_source(block)
                for t in source:
                    if not start_pred(t):
                        yield t
                        for t in source:
                            yield t
        else:
            source_start = token_source
        
        # where to end
        if end:
            end_block = document.block(end)
            end_pos = end - document.position(end_block)
            def source_end(source):
                for t in source:
                    if end_pred(t):
                        break
                    yield t
        
        # generate the tokens
        def generator():
            source = source_start
            block = start_block
            if end:
                while block != end_block:
                    yield block, source(block)
                    source = token_source
                    block = document.next_block(block)
                yield block, source_end(source(block))
            else:
                for block in document.blocks_forward(start_block):
                    yield block, source(block)
                    source = token_source
        gen = generator()
        
        # initialize block and tokens
        for self.block, self.tokens in gen:
            break
        # keep them going after the first line
        def g():
            for t in self.tokens:
                yield t
            for self.block, self.tokens in gen:
                for t in self.tokens:
                    yield t
        self._gen = g()
    
    def __iter__(self):
        return self._gen
    
    def __next__(self):
        return self._gen.next()
    
    next = __next__
    
    def document(self):
        """Return our Document."""
        return self._doc
    
    def slice(self, token, start=0, end=None):
        """Returns a slice for the token in the current block."""
        return self._doc.slice(self.block, token, start, end)
    
    def position(self, token):
        """Returns the position of the token in the current block."""
        return self._doc.position(self.block) + token.pos
    
    def consume(self, iterable, position):
        """Consumes iterable (supposed to be reading from us) until position.
        
        Returns the last token if that overlaps position.
        
        """
        if self._doc.position(self.block) < position:
            for t in iterable:
                pos = self.position(t)
                end = pos + len(t)
                if end == position:
                    return
                elif end > position:
                    if pos < position:
                        return t
                    return

