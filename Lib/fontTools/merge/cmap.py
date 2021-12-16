# Copyright 2013 Google, Inc. All Rights Reserved.
#
# Google Author(s): Behdad Esfahbod, Roozbeh Pournader

from fontTools.merge.unicode import *
from fontTools.pens.recordingPen import DecomposingRecordingPen
import logging


log = logging.getLogger("fontTools.merge")


def _glyphsAreSame(glyphSet1, glyphSet2, glyph1, glyph2,
				   advanceTolerance=.05,
				   advanceToleranceEmpty=.20):
	pen1 = DecomposingRecordingPen(glyphSet1)
	pen2 = DecomposingRecordingPen(glyphSet2)
	g1 = glyphSet1[glyph1]
	g2 = glyphSet2[glyph2]
	g1.draw(pen1)
	g2.draw(pen2)
	if pen1.value != pen2.value:
		return False
	# Allow more width tolerance for glyphs with no ink
	tolerance = advanceTolerance if pen1.value else advanceToleranceEmpty
    # TODO Warn if advances not the same but within tolerance.
	if abs(g1.width - g2.width) > g1.width * tolerance:
		return False
	if hasattr(g1, 'height') and g1.height is not None:
		if abs(g1.height - g2.height) > g1.height * tolerance:
			return False
	return True

# Valid (format, platformID, platEncID) triplets for cmap subtables containing
# Unicode BMP-only and Unicode Full Repertoire semantics.
# Cf. OpenType spec for "Platform specific encodings":
# https://docs.microsoft.com/en-us/typography/opentype/spec/name
class CmapUnicodePlatEncodings:
	BMP = {(4, 3, 1), (4, 0, 3), (4, 0, 4), (4, 0, 6)}
	FullRepertoire = {(12, 3, 10), (12, 0, 4), (12, 0, 6)}


def compute_mega_cmap(merger, tables):
	# TODO Handle format=14.
	# Only merge format 4 and 12 Unicode subtables, ignores all other subtables
	# If there is a format 12 table for a font, ignore the format 4 table of it
	cmapTables = []
	for fontIdx,table in enumerate(tables):
		format4 = None
		format12 = None
		for subtable in table.tables:
			properties = (subtable.format, subtable.platformID, subtable.platEncID)
			if properties in CmapUnicodePlatEncodings.BMP:
				format4 = subtable
			elif properties in CmapUnicodePlatEncodings.FullRepertoire:
				format12 = subtable
			else:
				log.warning(
					"Dropped cmap subtable from font [%s]:\t"
					"format %2s, platformID %2s, platEncID %2s",
					fontIdx, subtable.format, subtable.platformID, subtable.platEncID
				)
		if format12 is not None:
			cmapTables.append((format12, fontIdx))
		elif format4 is not None:
			cmapTables.append((format4, fontIdx))

	# Build the unicode mapping
	merger.cmap = cmap = {}
	fontIndexForGlyph = {}
	glyphSets = [None for f in merger.fonts] if hasattr(merger, 'fonts') else None
	for table,fontIdx in cmapTables:
		# handle duplicates
		for uni,gid in table.cmap.items():
			oldgid = cmap.get(uni, None)
			if oldgid is None:
				cmap[uni] = gid
				fontIndexForGlyph[gid] = fontIdx
			elif is_Default_Ignorable(uni) or uni in (0x25CC,): # U+25CC DOTTED CIRCLE
				continue
			elif oldgid != gid:
				# Char previously mapped to oldgid, now to gid.
				# Record, to fix up in GSUB 'locl' later.
				if merger.duplicateGlyphsPerFont[fontIdx].get(oldgid) is None:
					if glyphSets is not None:
						oldFontIdx = fontIndexForGlyph[oldgid]
						for idx in (fontIdx, oldFontIdx):
							if glyphSets[idx] is None:
								glyphSets[idx] = merger.fonts[idx].getGlyphSet()
						#if _glyphsAreSame(glyphSets[oldFontIdx], glyphSets[fontIdx], oldgid, gid):
						#	continue
					merger.duplicateGlyphsPerFont[fontIdx][oldgid] = gid
				elif merger.duplicateGlyphsPerFont[fontIdx][oldgid] != gid:
					# Char previously mapped to oldgid but oldgid is already remapped to a different
					# gid, because of another Unicode character.
					# TODO: Try harder to do something about these.
					log.warning("Dropped mapping from codepoint %#06X to glyphId '%s'", uni, gid)


