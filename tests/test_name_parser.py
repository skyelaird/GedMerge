"""Tests for the comprehensive name parser."""

import pytest
from gedmerge.utils.name_parser import NameParser, ParsedName


class TestSurnameParticleDetection:
    """Test detection of surname particles (von, de, van, etc.)."""

    def test_german_von(self):
        assert NameParser.is_surname_particle('von')
        assert NameParser.is_surname_particle('vom')
        assert NameParser.is_surname_particle('zu')
        assert NameParser.is_surname_particle('im')

    def test_french_de(self):
        assert NameParser.is_surname_particle('de')
        assert NameParser.is_surname_particle('du')
        assert NameParser.is_surname_particle('des')
        assert NameParser.is_surname_particle("d'")

    def test_dutch_van(self):
        assert NameParser.is_surname_particle('van')
        assert NameParser.is_surname_particle('van de')
        assert NameParser.is_surname_particle('van der')

    def test_case_insensitive(self):
        assert NameParser.is_surname_particle('VON')
        assert NameParser.is_surname_particle('De')
        assert NameParser.is_surname_particle('VAN')

    def test_not_particles(self):
        assert not NameParser.is_surname_particle('Thomas')
        assert not NameParser.is_surname_particle('Smith')
        assert not NameParser.is_surname_particle('Franconia')


class TestPrefixDetection:
    """Test detection of honorific prefixes."""

    def test_german_prefixes(self):
        assert NameParser.is_prefix('Frau')
        assert NameParser.is_prefix('Herr')
        assert NameParser.is_prefix('Fräulein')

    def test_english_prefixes(self):
        assert NameParser.is_prefix('Sir')
        assert NameParser.is_prefix('Lady')
        assert NameParser.is_prefix('Lord')
        assert NameParser.is_prefix('Mr')
        assert NameParser.is_prefix('Mrs')

    def test_prefix_with_period(self):
        assert NameParser.is_prefix('Mr.')
        assert NameParser.is_prefix('Mrs.')
        assert NameParser.is_prefix('Dr.')

    def test_not_prefix(self):
        assert not NameParser.is_prefix('Thomas')
        assert not NameParser.is_prefix('von')


class TestQuotedEpithetExtraction:
    """Test extraction of quoted epithets/nicknames."""

    def test_single_quoted_epithet(self):
        text = "Thomas 'The Wise' II"
        cleaned, epithets = NameParser.extract_quoted_epithets(text)
        assert cleaned == "Thomas  II"
        assert epithets == ["The Wise"]

    def test_double_quoted_epithet(self):
        text = 'Thomas "The Great" II'
        cleaned, epithets = NameParser.extract_quoted_epithets(text)
        assert "Thomas" in cleaned
        assert "II" in cleaned
        assert epithets == ["The Great"]

    def test_multiple_epithets(self):
        text = "Thomas 'The Wise' 'The Just'"
        cleaned, epithets = NameParser.extract_quoted_epithets(text)
        assert "Thomas" in cleaned
        assert epithets == ["The Wise", "The Just"]

    def test_no_epithets(self):
        text = "Thomas II"
        cleaned, epithets = NameParser.extract_quoted_epithets(text)
        assert cleaned == "Thomas II"
        assert epithets == []


class TestOrdinalExtraction:
    """Test extraction of Roman numeral ordinals."""

    def test_roman_numeral_ii(self):
        text = "Thomas II"
        cleaned, ordinal = NameParser.extract_ordinal(text)
        assert cleaned == "Thomas"
        assert ordinal == "II"

    def test_roman_numeral_iii(self):
        text = "Edward III"
        cleaned, ordinal = NameParser.extract_ordinal(text)
        assert cleaned == "Edward"
        assert ordinal == "III"

    def test_roman_numeral_iv(self):
        text = "Henry IV"
        cleaned, ordinal = NameParser.extract_ordinal(text)
        assert cleaned == "Henry"
        assert ordinal == "IV"

    def test_no_ordinal(self):
        text = "Thomas"
        cleaned, ordinal = NameParser.extract_ordinal(text)
        assert cleaned == "Thomas"
        assert ordinal is None


class TestNobilitySuffixExtraction:
    """Test extraction of nobility titles as suffixes."""

    def test_ordinal_baron(self):
        text = "Thomas 1st Baron"
        cleaned, suffix = NameParser.extract_nobility_suffix(text)
        assert "Thomas" in cleaned
        assert suffix == "1st Baron"

    def test_ordinal_baron_of_place(self):
        text = "Thomas 10th Baron of Ferniehurst"
        cleaned, suffix = NameParser.extract_nobility_suffix(text)
        assert "Thomas" in cleaned
        assert "Baron" in suffix
        assert "Ferniehurst" in suffix

    def test_earl_title(self):
        text = "Robert Earl of Essex"
        cleaned, suffix = NameParser.extract_nobility_suffix(text)
        assert "Robert" in cleaned
        assert "Earl" in suffix

    def test_heir_title(self):
        text = "Gwenllian Heiress of Powys"
        cleaned, suffix = NameParser.extract_nobility_suffix(text)
        assert "Gwenllian" in cleaned
        assert "Heiress of Powys" in suffix

    def test_no_nobility_suffix(self):
        text = "Thomas Smith"
        cleaned, suffix = NameParser.extract_nobility_suffix(text)
        assert cleaned == "Thomas Smith"
        assert suffix is None


class TestPrefixExtraction:
    """Test extraction of honorific prefixes."""

    def test_frau_prefix(self):
        text = "Frau Gerberga"
        cleaned, prefix = NameParser.extract_prefix(text)
        assert cleaned == "Gerberga"
        assert prefix == "Frau"

    def test_sir_prefix(self):
        text = "Sir Thomas"
        cleaned, prefix = NameParser.extract_prefix(text)
        assert cleaned == "Thomas"
        assert prefix == "Sir"

    def test_lady_prefix(self):
        text = "Lady Margaret"
        cleaned, prefix = NameParser.extract_prefix(text)
        assert cleaned == "Margaret"
        assert prefix == "Lady"

    def test_no_prefix(self):
        text = "Thomas Smith"
        cleaned, prefix = NameParser.extract_prefix(text)
        assert cleaned == "Thomas Smith"
        assert prefix is None


class TestSurnameWithParticleExtraction:
    """Test extraction of surnames with particles."""

    def test_von_franconia(self):
        text = "Gerberga von Franconia"
        remaining, surname = NameParser.extract_surname_with_particle(text)
        assert remaining == "Gerberga"
        assert surname == "von Franconia"

    def test_de_france(self):
        text = "Philippe de France"
        remaining, surname = NameParser.extract_surname_with_particle(text)
        assert remaining == "Philippe"
        assert surname == "de France"

    def test_van_der_berg(self):
        text = "Jan van der Berg"
        remaining, surname = NameParser.extract_surname_with_particle(text)
        assert remaining == "Jan"
        # Note: will match at "van" not "van der"
        assert "van" in surname
        assert "Berg" in surname

    def test_no_particle(self):
        text = "Thomas Smith"
        remaining, surname = NameParser.extract_surname_with_particle(text)
        assert remaining == "Thomas Smith"
        assert surname is None


class TestParseGivnField:
    """Test parsing of GIVN fields with complex content."""

    def test_simple_given_name(self):
        result = NameParser.parse_givn_field("Thomas")
        assert result.given == "Thomas"
        assert result.ordinal is None
        assert result.nickname is None
        assert result.suffix is None

    def test_given_with_ordinal(self):
        result = NameParser.parse_givn_field("Thomas II")
        assert result.given == "Thomas II"
        assert result.ordinal == "II"

    def test_thomas_the_wise_baron(self):
        """Test user's example: Thomas II 'The Wise' 1st Baron"""
        result = NameParser.parse_givn_field("Thomas II 'The Wise' 1st Baron")
        assert result.given == "Thomas II"
        assert result.ordinal == "II"
        assert result.nickname == "The Wise"
        assert "The Wise" in result.epithets
        assert result.suffix == "1st Baron"

    def test_given_with_epithet(self):
        result = NameParser.parse_givn_field("Edward 'Longshanks'")
        assert "Edward" in result.given
        assert result.nickname == "Longshanks"
        assert "Longshanks" in result.epithets

    def test_given_with_suffix(self):
        result = NameParser.parse_givn_field("Robert Earl of Essex")
        assert "Robert" in result.given
        assert "Earl" in result.suffix


class TestParseFieldWithSurnameParticle:
    """Test parsing fields that incorrectly contain surname particles."""

    def test_frau_gerberga_von_franconia(self):
        """Test user's example: Frau Gerberga von Franconia (tagged as NICK)"""
        result = NameParser.parse_field_with_surname_particle(
            "Frau Gerberga von Franconia",
            field_type='NICK'
        )
        assert result.prefix == "Frau"
        assert result.given == "Gerberga"
        assert result.surname == "von Franconia"

    def test_dame_marie_de_france(self):
        result = NameParser.parse_field_with_surname_particle(
            "Dame Marie de France",
            field_type='NICK'
        )
        assert result.prefix == "Dame"
        assert result.given == "Marie"
        assert result.surname == "de France"

    def test_no_particle_in_nickname(self):
        result = NameParser.parse_field_with_surname_particle(
            "The Great",
            field_type='NICK'
        )
        assert result.given == "The Great"
        assert result.surname is None


class TestParseNameField:
    """Test parsing of full NAME fields in GEDCOM format."""

    def test_simple_name(self):
        result = NameParser.parse_name_field("Thomas /Smith/")
        assert result.given == "Thomas"
        assert result.surname == "Smith"

    def test_name_with_prefix(self):
        result = NameParser.parse_name_field("Sir Thomas /Smith/")
        assert result.prefix == "Sir"
        assert result.given == "Thomas"
        assert result.surname == "Smith"

    def test_name_with_suffix(self):
        result = NameParser.parse_name_field("Thomas /Smith/ 1st Baron")
        assert result.given == "Thomas"
        assert result.surname == "Smith"
        assert result.suffix == "1st Baron"

    def test_name_with_von(self):
        result = NameParser.parse_name_field("Frau Gerberga /von Franconia/")
        assert result.prefix == "Frau"
        assert result.given == "Gerberga"
        assert result.surname == "von Franconia"

    def test_complex_name(self):
        result = NameParser.parse_name_field("Sir Thomas II 'The Wise' /Smith/ 1st Baron")
        assert result.prefix == "Sir"
        assert result.given == "Thomas II"
        assert result.ordinal == "II"
        assert result.surname == "Smith"
        assert result.nickname == "The Wise"
        assert result.suffix == "1st Baron"


class TestNormalizeNameComponents:
    """Test normalization of name components."""

    def test_normalize_simple(self):
        result = NameParser.normalize_name_components(
            given="Thomas",
            surname="Smith"
        )
        assert result.given == "Thomas"
        assert result.surname == "Smith"

    def test_normalize_complex_given(self):
        result = NameParser.normalize_name_components(
            given="Thomas II 'The Wise' 1st Baron",
            surname="Smith"
        )
        assert result.given == "Thomas II"
        assert result.ordinal == "II"
        assert result.nickname == "The Wise"
        assert result.suffix == "1st Baron"
        assert result.surname == "Smith"

    def test_normalize_misclassified_nickname(self):
        """Test fixing nickname that contains surname particle."""
        result = NameParser.normalize_name_components(
            given="Gerberga",
            nickname="von Franconia"  # Incorrectly classified
        )
        assert result.given == "Gerberga"
        assert result.surname == "von Franconia"
        # Should NOT have nickname since it was reclassified as surname
        assert result.nickname is None

    def test_normalize_misclassified_nickname_with_prefix(self):
        """Test fixing nickname with prefix and surname particle."""
        result = NameParser.normalize_name_components(
            nickname="Frau Gerberga von Franconia"  # Incorrectly classified as nickname
        )
        assert result.prefix == "Frau"
        assert result.given == "Gerberga"
        assert result.surname == "von Franconia"
        assert result.nickname is None


class TestHasSurnameParticle:
    """Test detection of surname particles in text."""

    def test_has_von(self):
        assert NameParser.has_surname_particle("von Franconia")
        assert NameParser.has_surname_particle("Gerberga von Franconia")

    def test_has_de(self):
        assert NameParser.has_surname_particle("de France")
        assert NameParser.has_surname_particle("Marie de France")

    def test_has_van(self):
        assert NameParser.has_surname_particle("van der Berg")

    def test_no_particle(self):
        assert not NameParser.has_surname_particle("Thomas Smith")
        assert not NameParser.has_surname_particle("The Great")


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_empty_string(self):
        result = NameParser.parse_givn_field("")
        assert result.given is None

    def test_whitespace_only(self):
        result = NameParser.parse_givn_field("   ")
        assert result.given is None or result.given == ""

    def test_surname_only_in_name(self):
        result = NameParser.parse_name_field("/Smith/")
        assert result.surname == "Smith"
        assert result.given is None

    def test_no_surname_in_name(self):
        result = NameParser.parse_name_field("Thomas")
        assert result.given == "Thomas"
        assert result.surname is None


class TestFrenchNameHandling:
    """Test French-specific name parsing rules."""

    def test_m_abbreviation_female_names(self):
        """Test that M. is replaced with Marie for female names."""
        result = NameParser.parse_givn_field("M. Anne", sex='F')
        assert result.given == "Marie Anne"
        assert result.prefix is None

    def test_m_abbreviation_male_names(self):
        """Test that M. remains a prefix for male names."""
        result = NameParser.parse_givn_field("M. Jean", sex='M')
        assert result.given == "Jean"
        assert result.prefix == "M."

    def test_m_in_name_field_female(self):
        """Test M. in full NAME field for females."""
        result = NameParser.parse_name_field("M. Anne /de Bréval/", sex='F')
        assert result.given == "Marie Anne"
        assert result.surname == "de Bréval"
        assert result.prefix is None

    def test_seigneur_as_suffix(self):
        """Test that Seigneur is treated as a suffix, not prefix."""
        result = NameParser.parse_field_with_surname_particle(
            "Pierre Seigneur d'Amboise et Chaumont"
        )
        assert result.given == "Pierre"
        assert result.suffix == "Seigneur d'Amboise et Chaumont"
        assert result.prefix is None or "Seigneur" not in (result.prefix or "")

    def test_de_particle_in_surname(self):
        """Test that 'de' particles stay with surnames."""
        result = NameParser.parse_name_field("Anne /de Bréval/")
        assert result.given == "Anne"
        assert result.surname == "de Bréval"

    def test_complex_french_female_name(self):
        """Test complex French female name with M. and de particle."""
        result = NameParser.parse_name_field("M. Marie /de France/", sex='F')
        assert result.given == "Marie Marie"
        assert result.surname == "de France"
        assert result.prefix is None


class TestGermanNameHandling:
    """Test German-specific name parsing rules."""

    def test_von_particle_in_surname(self):
        """Test that 'von' particles stay with surnames."""
        result = NameParser.parse_name_field("Chadalhoh /von Ogiers-Isengau/")
        assert result.given == "Chadalhoh"
        assert result.surname == "von Ogiers-Isengau"

    def test_von_in_nickname_field(self):
        """Test von particle extracted from misclassified nickname field."""
        result = NameParser.parse_field_with_surname_particle(
            "Chadalhoh von OGIERS-ISENGAU"
        )
        assert "Chadalhoh" in result.given or result.given == "Chadalhoh"
        # Should recognize von as surname particle


class TestTitleSuffixes:
    """Test title suffix extraction."""

    def test_is_title_suffix(self):
        """Test title suffix detection."""
        assert NameParser.is_title_suffix("Seigneur")
        assert not NameParser.is_title_suffix("Marie")

    def test_extract_title_suffix(self):
        """Test title suffix extraction."""
        text, suffix = NameParser.extract_title_suffix("Pierre Seigneur d'Amboise")
        assert text == "Pierre"
        assert suffix == "Seigneur d'Amboise"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
