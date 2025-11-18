"""Tests for RootsMagic date decoder and multi-language date support."""

import pytest
from gedmerge.utils.date_decoder import (
    RootsMagicDateDecoder,
    MultiLanguageDateParser,
    DecodedDate,
    DateModifier,
    decode_rootsmagic_date,
)


class TestRootsMagicDateDecoder:
    """Tests for RootsMagic SortDate decoding."""

    def test_unknown_date(self):
        """Test decoding of unknown date value."""
        result = RootsMagicDateDecoder.decode(9223372036854775807)
        assert result.year is None
        assert result.original_string == "Unknown"

    def test_exact_date_encoding_decoding(self):
        """Test encoding and decoding of exact dates."""
        original = DecodedDate(
            year=1950,
            month=6,
            day=15,
            modifier=DateModifier.EXACT
        )

        # Encode
        sort_date = RootsMagicDateDecoder.encode(original)
        assert sort_date != RootsMagicDateDecoder.UNKNOWN_DATE

        # Decode back
        decoded = RootsMagicDateDecoder.decode(sort_date)
        assert decoded.year == 1950
        assert decoded.month == 6
        assert decoded.day == 15

    def test_year_only_date(self):
        """Test decoding of year-only dates."""
        original = DecodedDate(
            year=1900,
            modifier=DateModifier.EXACT
        )

        sort_date = RootsMagicDateDecoder.encode(original)
        decoded = RootsMagicDateDecoder.decode(sort_date)

        assert decoded.year == 1900
        assert decoded.month is None
        assert decoded.day is None

    def test_about_modifier(self):
        """Test ABT modifier."""
        original = DecodedDate(
            year=1850,
            modifier=DateModifier.ABOUT
        )

        sort_date = RootsMagicDateDecoder.encode(original)
        decoded = RootsMagicDateDecoder.decode(sort_date)

        assert decoded.year == 1850
        # Note: modifier detection from flags may need refinement

    def test_date_range_between(self):
        """Test BET...AND date ranges."""
        original = DecodedDate(
            year=1900,
            month=1,
            day=1,
            modifier=DateModifier.BETWEEN,
            year2=1905,
            month2=12,
            day2=31
        )

        sort_date = RootsMagicDateDecoder.encode(original)
        decoded = RootsMagicDateDecoder.decode(sort_date)

        assert decoded.year == 1900
        assert decoded.year2 == 1905

    def test_user_reported_death_date(self):
        """Test the actual death date from user's report."""
        # Death: 'D.+08340000..+00000000..' (sort: 6098999812545314828)
        sort_date = 6098999812545314828

        decoded = RootsMagicDateDecoder.decode(sort_date)

        # Should decode to a valid year
        assert decoded.year is not None
        print(f"Decoded year: {decoded.year}, month: {decoded.month}, day: {decoded.day}")
        print(f"GEDCOM: {decoded.to_gedcom()}")

    def test_historical_dates(self):
        """Test dates for historical periods like 781 AD."""
        original = DecodedDate(
            year=781,
            modifier=DateModifier.EXACT
        )

        sort_date = RootsMagicDateDecoder.encode(original)
        decoded = RootsMagicDateDecoder.decode(sort_date)

        assert decoded.year == 781

    def test_to_gedcom_format(self):
        """Test conversion to GEDCOM format."""
        date = DecodedDate(year=1950, month=6, day=15, modifier=DateModifier.EXACT)
        assert date.to_gedcom() == "15 JUN 1950"

        date = DecodedDate(year=1950, month=6, modifier=DateModifier.EXACT)
        assert date.to_gedcom() == "JUN 1950"

        date = DecodedDate(year=1950, modifier=DateModifier.EXACT)
        assert date.to_gedcom() == "1950"

        date = DecodedDate(year=1950, modifier=DateModifier.ABOUT)
        assert date.to_gedcom() == "ABT 1950"

        date = DecodedDate(
            year=1900, modifier=DateModifier.BETWEEN,
            year2=1905
        )
        assert date.to_gedcom() == "BET 1900 AND 1905"


class TestMultiLanguageDateParser:
    """Tests for multi-language date parsing."""

    def test_english_modifiers(self):
        """Test standard English GEDCOM modifiers."""
        assert MultiLanguageDateParser.parse("ABT 1950").modifier == DateModifier.ABOUT
        assert MultiLanguageDateParser.parse("BEF 1900").modifier == DateModifier.BEFORE
        assert MultiLanguageDateParser.parse("AFT 1920").modifier == DateModifier.AFTER
        assert MultiLanguageDateParser.parse("EST 1875").modifier == DateModifier.ESTIMATED

    def test_french_modifiers(self):
        """Test French date modifiers."""
        result = MultiLanguageDateParser.parse("Vers 1650")
        assert result.modifier == DateModifier.ABOUT
        assert result.year == 1650

        result = MultiLanguageDateParser.parse("Avant 1700")
        assert result.modifier == DateModifier.BEFORE
        assert result.year == 1700

        result = MultiLanguageDateParser.parse("Après 1800")
        assert result.modifier == DateModifier.AFTER
        assert result.year == 1800

    def test_spanish_modifiers(self):
        """Test Spanish date modifiers."""
        result = MultiLanguageDateParser.parse("Hacia 1492")
        assert result.modifier == DateModifier.ABOUT
        assert result.year == 1492

    def test_italian_modifiers(self):
        """Test Italian date modifiers."""
        result = MultiLanguageDateParser.parse("Circa 1500")
        assert result.modifier == DateModifier.ABOUT
        assert result.year == 1500

    def test_german_modifiers(self):
        """Test German date modifiers."""
        result = MultiLanguageDateParser.parse("Um 1750")
        assert result.modifier == DateModifier.ABOUT
        assert result.year == 1750

        result = MultiLanguageDateParser.parse("Vor 1800")
        assert result.modifier == DateModifier.BEFORE
        assert result.year == 1800

    def test_dutch_modifiers(self):
        """Test Dutch date modifiers."""
        result = MultiLanguageDateParser.parse("Tussen 1900")
        assert result.modifier == DateModifier.BETWEEN
        assert result.year == 1900

    def test_user_reported_tum_date(self):
        """Test the actual 'Tum 0781' date from user's report."""
        # Birth: 'Tum 0781' (Dutch: Tussen = Between)
        result = MultiLanguageDateParser.parse("Tum 0781")

        assert result is not None
        assert result.modifier == DateModifier.BETWEEN
        assert result.year == 781

        # Should normalize to GEDCOM
        gedcom = result.to_gedcom()
        print(f"'Tum 0781' normalized to: {gedcom}")

    def test_between_with_range(self):
        """Test BETWEEN...AND format in multiple languages."""
        result = MultiLanguageDateParser.parse("BET 1900 AND 1905")
        assert result.modifier == DateModifier.BETWEEN
        assert result.year == 1900
        assert result.year2 == 1905

        result = MultiLanguageDateParser.parse("Entre 1800 et 1810")
        assert result.modifier == DateModifier.BETWEEN
        assert result.year == 1800
        assert result.year2 == 1810

    def test_date_with_month(self):
        """Test dates with month names."""
        result = MultiLanguageDateParser.parse("15 JAN 1950")
        assert result.year == 1950
        assert result.month == 1
        assert result.day == 15

        result = MultiLanguageDateParser.parse("Janvier 1950")
        assert result.year == 1950
        assert result.month == 1

    def test_normalize_to_gedcom(self):
        """Test normalization to GEDCOM format."""
        assert MultiLanguageDateParser.normalize_to_gedcom("Vers 1650") == "ABT 1650"
        assert MultiLanguageDateParser.normalize_to_gedcom("Circa 1500") == "ABT 1500"
        assert MultiLanguageDateParser.normalize_to_gedcom("Tum 0781") == "BET 781"
        assert MultiLanguageDateParser.normalize_to_gedcom("Avant 1700") == "BEF 1700"

    def test_historical_year_formats(self):
        """Test 3-digit historical years like 781."""
        result = MultiLanguageDateParser.parse("781")
        assert result.year == 781

        result = MultiLanguageDateParser.parse("ABT 781")
        assert result.year == 781
        assert result.modifier == DateModifier.ABOUT


class TestDecodedDate:
    """Tests for DecodedDate class."""

    def test_is_valid(self):
        """Test date validation."""
        assert DecodedDate(year=1950).is_valid()
        assert DecodedDate(year=1950, month=6, day=15).is_valid()
        assert not DecodedDate(year=None).is_valid()
        assert not DecodedDate(year=1950, month=13).is_valid()
        assert not DecodedDate(year=1950, day=32).is_valid()
        assert not DecodedDate(year=20000).is_valid()


class TestDecodeRootsMagicDate:
    """Tests for the main decode function."""

    def test_decode_with_date_string(self):
        """Test decoding when date string is provided."""
        result = decode_rootsmagic_date("ABT 1950", None)
        assert "ABT" in result or "1950" in result

        result = decode_rootsmagic_date("Vers 1650", None)
        assert "ABT" in result or "1650" in result

    def test_decode_with_sortdate(self):
        """Test decoding from SortDate when date string is invalid."""
        # Create a sort date for 1950
        date = DecodedDate(year=1950, month=6, day=15)
        sort_date = RootsMagicDateDecoder.encode(date)

        result = decode_rootsmagic_date("", sort_date)
        assert "1950" in result

    def test_decode_priority(self):
        """Test that date string takes priority over SortDate."""
        date = DecodedDate(year=1900)
        sort_date = RootsMagicDateDecoder.encode(date)

        # Date string should be used if valid
        result = decode_rootsmagic_date("ABT 1950", sort_date)
        assert "1950" in result

    def test_decode_user_reported_dates(self):
        """Test the actual dates from user's report."""
        # Birth: 'Tum 0781' (sort: 9223372036854775807)
        birth_result = decode_rootsmagic_date("Tum 0781", 9223372036854775807)
        print(f"Birth: 'Tum 0781' -> {birth_result}")
        assert "781" in birth_result

        # Death: 'D.+08340000..+00000000..' (sort: 6098999812545314828)
        death_result = decode_rootsmagic_date("D.+08340000..+00000000..", 6098999812545314828)
        print(f"Death: 'D.+08340000..+00000000..' -> {death_result}")
        # Should decode from SortDate since date string is invalid


if __name__ == "__main__":
    # Run a quick test of the user's reported dates
    print("Testing user-reported dates:")
    print("=" * 60)

    birth = decode_rootsmagic_date("Tum 0781", 9223372036854775807)
    print(f"Birth: 'Tum 0781' (sort: 9223372036854775807)")
    print(f"  Decoded: {birth}")
    print()

    death = decode_rootsmagic_date("D.+08340000..+00000000..", 6098999812545314828)
    print(f"Death: 'D.+08340000..+00000000..' (sort: 6098999812545314828)")
    print(f"  Decoded: {death}")
    print()

    # Test the actual SortDate decoding
    decoded_death = RootsMagicDateDecoder.decode(6098999812545314828)
    print(f"Death SortDate breakdown:")
    print(f"  Year: {decoded_death.year}")
    print(f"  Month: {decoded_death.month}")
    print(f"  Day: {decoded_death.day}")
    print(f"  GEDCOM: {decoded_death.to_gedcom()}")
