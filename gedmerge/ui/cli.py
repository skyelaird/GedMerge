"""Command-line interface for GEDMerge."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from ..core.gedcom_parser import GedcomParser


def print_statistics(parser: GedcomParser) -> None:
    """Print statistics about the loaded GEDCOM file.

    Args:
        parser: GedcomParser instance with loaded data
    """
    stats = parser.get_statistics()

    print("\n" + "=" * 60)
    print("GEDCOM FILE STATISTICS")
    print("=" * 60)
    print(f"Total Individuals:      {stats['num_individuals']:,}")
    print(f"Total Families:         {stats['num_families']:,}")
    print()
    print(f"Males:                  {stats['num_males']:,}")
    print(f"Females:                {stats['num_females']:,}")
    print(f"Unknown Gender:         {stats['num_unknown_sex']:,}")

    if 'earliest_year' in stats and 'latest_year' in stats:
        print()
        print(f"Date Range:             {stats['earliest_year']} - {stats['latest_year']}")
        print(f"Span:                   {stats['latest_year'] - stats['earliest_year']} years")

    print("=" * 60 + "\n")


def print_sample_individuals(parser: GedcomParser, count: int = 5) -> None:
    """Print a sample of individuals from the file.

    Args:
        parser: GedcomParser instance with loaded data
        count: Number of individuals to display
    """
    if not parser.individuals:
        print("No individuals found in file.")
        return

    print("\nSAMPLE INDIVIDUALS:")
    print("-" * 60)

    for i, person in enumerate(list(parser.individuals.values())[:count]):
        print(f"{i + 1}. {person}")
        if person.get_birth_place():
            print(f"   Born: {person.get_birth_place()}")

    if len(parser.individuals) > count:
        print(f"\n... and {len(parser.individuals) - count} more individuals")

    print("-" * 60 + "\n")


def analyze_command(args: argparse.Namespace) -> int:
    """Execute the analyze command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    filepath = args.file

    # Check if file exists
    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return 1

    try:
        print(f"Loading GEDCOM file: {filepath}")
        parser = GedcomParser()
        parser.load_gedcom(filepath)

        # Print statistics
        print_statistics(parser)

        # Print sample individuals if requested
        if args.show_samples:
            print_sample_individuals(parser, count=args.sample_count)

        return 0

    except Exception as e:
        print(f"Error processing file: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='gedmerge',
        description='A tool to find and merge duplicate people in GEDCOM genealogy files.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.1.0'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands'
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze a GEDCOM file and display statistics'
    )
    analyze_parser.add_argument(
        'file',
        help='Path to the GEDCOM file'
    )
    analyze_parser.add_argument(
        '-s', '--show-samples',
        action='store_true',
        help='Show sample individuals from the file'
    )
    analyze_parser.add_argument(
        '-n', '--sample-count',
        type=int,
        default=5,
        help='Number of sample individuals to display (default: 5)'
    )

    # Find duplicates command (placeholder for Phase 2)
    find_parser = subparsers.add_parser(
        'find-duplicates',
        help='Find potential duplicate individuals (Coming in Phase 2)'
    )
    find_parser.add_argument(
        'file',
        help='Path to the GEDCOM file'
    )

    # Merge command (placeholder for Phase 3)
    merge_parser = subparsers.add_parser(
        'merge',
        help='Merge duplicate individuals (Coming in Phase 3)'
    )
    merge_parser.add_argument(
        'file',
        help='Path to the GEDCOM file'
    )
    merge_parser.add_argument(
        '-o', '--output',
        help='Output file path for merged GEDCOM'
    )

    return parser


def main(argv: Optional[list] = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # If no command specified, print help
    if not args.command:
        parser.print_help()
        return 0

    # Execute the appropriate command
    if args.command == 'analyze':
        return analyze_command(args)
    elif args.command == 'find-duplicates':
        print("Find duplicates functionality coming in Phase 2!")
        return 0
    elif args.command == 'merge':
        print("Merge functionality coming in Phase 3!")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
