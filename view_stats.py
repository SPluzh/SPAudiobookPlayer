"""
Simple CLI tool to view listening statistics
Usage: python view_stats.py [options]
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager


def format_duration(seconds):
    """Format seconds into human-readable duration"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def show_daily_stats(db, audiobook_id=None, days=7):
    """Show daily statistics for the last N days"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days-1)
    
    stats = db.get_daily_stats(
        audiobook_id=audiobook_id,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
    
    if not stats:
        print("No listening data found for the specified period.")
        return
    
    print(f"\n{'='*70}")
    print(f"DAILY LISTENING STATISTICS (Last {days} days)")
    print(f"{'='*70}")
    print(f"{'Date':<12} {'Book':<30} {'Time':<15} {'Sessions':<10}")
    print(f"{'-'*70}")
    
    total_seconds = 0
    total_sessions = 0
    
    for stat in stats:
        book_name = stat['audiobook_name'] or 'Unknown'
        if len(book_name) > 28:
            book_name = book_name[:25] + '...'
        
        print(f"{stat['date']:<12} {book_name:<30} {format_duration(stat['total_seconds']):<15} {stat['session_count']:<10}")
        total_seconds += stat['total_seconds']
        total_sessions += stat['session_count']
    
    print(f"{'-'*70}")
    print(f"{'TOTAL':<42} {format_duration(total_seconds):<15} {total_sessions:<10}")
    print(f"{'='*70}\n")


def show_monthly_stats(db, audiobook_id=None, months=3):
    """Show monthly statistics"""
    stats = db.get_monthly_stats(audiobook_id=audiobook_id)
    
    if not stats:
        print("No listening data found.")
        return
    
    # Sort by month descending and limit
    stats = sorted(stats, key=lambda x: x['month'], reverse=True)[:months]
    
    print(f"\n{'='*70}")
    print(f"MONTHLY LISTENING STATISTICS")
    print(f"{'='*70}")
    print(f"{'Month':<12} {'Book':<30} {'Time':<15} {'Sessions':<10}")
    print(f"{'-'*70}")
    
    for stat in stats:
        book_name = stat['audiobook_name'] or 'Unknown'
        if len(book_name) > 28:
            book_name = book_name[:25] + '...'
        
        print(f"{stat['month']:<12} {book_name:<30} {format_duration(stat['total_seconds']):<15} {stat['session_count']:<10}")
    
    print(f"{'='*70}\n")


def show_yearly_stats(db, audiobook_id=None):
    """Show yearly statistics"""
    stats = db.get_yearly_stats(audiobook_id=audiobook_id)
    
    if not stats:
        print("No listening data found.")
        return
    
    # Sort by year descending
    stats = sorted(stats, key=lambda x: x['year'], reverse=True)
    
    print(f"\n{'='*70}")
    print(f"YEARLY LISTENING STATISTICS")
    print(f"{'='*70}")
    print(f"{'Year':<12} {'Book':<30} {'Time':<15} {'Sessions':<10}")
    print(f"{'-'*70}")
    
    for stat in stats:
        book_name = stat['audiobook_name'] or 'Unknown'
        if len(book_name) > 28:
            book_name = book_name[:25] + '...'
        
        print(f"{stat['year']:<12} {book_name:<30} {format_duration(stat['total_seconds']):<15} {stat['session_count']:<10}")
    
    print(f"{'='*70}\n")


def show_top_books(db, limit=10, period='all'):
    """Show top books by listening time"""
    if period == 'month':
        year = datetime.now().year
        month = datetime.now().month
        stats = db.get_monthly_stats(year=year, month=month)
        title = f"TOP {limit} BOOKS THIS MONTH ({year}-{month:02d})"
    elif period == 'year':
        year = datetime.now().year
        stats = db.get_yearly_stats(year=year)
        title = f"TOP {limit} BOOKS THIS YEAR ({year})"
    else:
        stats = db.get_yearly_stats()
        title = f"TOP {limit} BOOKS (ALL TIME)"
    
    if not stats:
        print("No listening data found.")
        return
    
    # Sort by total seconds and limit
    stats = sorted(stats, key=lambda x: x['total_seconds'], reverse=True)[:limit]
    
    print(f"\n{'='*70}")
    print(title)
    print(f"{'='*70}")
    print(f"{'#':<4} {'Book':<35} {'Time':<15} {'Sessions':<10}")
    print(f"{'-'*70}")
    
    for i, stat in enumerate(stats, 1):
        book_name = stat['audiobook_name'] or 'Unknown'
        if len(book_name) > 33:
            book_name = book_name[:30] + '...'
        
        print(f"{i:<4} {book_name:<35} {format_duration(stat['total_seconds']):<15} {stat['session_count']:<10}")
    
    print(f"{'='*70}\n")


def show_summary(db):
    """Show overall summary statistics"""
    # Get all yearly stats
    stats = db.get_yearly_stats()
    
    if not stats:
        print("No listening data found.")
        return
    
    total_seconds = sum(s['total_seconds'] for s in stats)
    total_sessions = sum(s['session_count'] for s in stats)
    unique_books = len(set(s['audiobook_id'] for s in stats))
    
    # Get today's stats
    today = datetime.now().strftime('%Y-%m-%d')
    today_stats = db.get_daily_stats(start_date=today, end_date=today)
    today_seconds = sum(s['total_seconds'] for s in today_stats)
    
    # Get this month's stats
    year = datetime.now().year
    month = datetime.now().month
    month_stats = db.get_monthly_stats(year=year, month=month)
    month_seconds = sum(s['total_seconds'] for s in month_stats)
    
    print(f"\n{'='*70}")
    print("LISTENING STATISTICS SUMMARY")
    print(f"{'='*70}")
    print(f"Total listening time:        {format_duration(total_seconds)} ({total_seconds/3600:.1f} hours)")
    print(f"Total sessions:              {total_sessions}")
    print(f"Unique books:                {unique_books}")
    print(f"Average per book:            {format_duration(total_seconds/unique_books if unique_books > 0 else 0)}")
    print(f"Average session length:      {format_duration(total_seconds/total_sessions if total_sessions > 0 else 0)}")
    print(f"-" * 70)
    print(f"Today:                       {format_duration(today_seconds)}")
    print(f"This month:                  {format_duration(month_seconds)}")
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='View audiobook listening statistics')
    parser.add_argument('--db', default='data/audiobooks.db', help='Path to database file')
    parser.add_argument('--daily', action='store_true', help='Show daily statistics')
    parser.add_argument('--monthly', action='store_true', help='Show monthly statistics')
    parser.add_argument('--yearly', action='store_true', help='Show yearly statistics')
    parser.add_argument('--top', action='store_true', help='Show top books')
    parser.add_argument('--summary', action='store_true', help='Show summary statistics')
    parser.add_argument('--days', type=int, default=7, help='Number of days for daily stats (default: 7)')
    parser.add_argument('--limit', type=int, default=10, help='Limit for top books (default: 10)')
    parser.add_argument('--period', choices=['all', 'month', 'year'], default='all', help='Period for top books')
    parser.add_argument('--book-id', type=int, help='Filter by specific audiobook ID')
    
    args = parser.parse_args()
    
    # Check if database exists
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    db = DatabaseManager(db_path)
    
    # If no specific option is given, show summary
    if not any([args.daily, args.monthly, args.yearly, args.top, args.summary]):
        args.summary = True
    
    # Show requested statistics
    if args.summary:
        show_summary(db)
    
    if args.daily:
        show_daily_stats(db, audiobook_id=args.book_id, days=args.days)
    
    if args.monthly:
        show_monthly_stats(db, audiobook_id=args.book_id)
    
    if args.yearly:
        show_yearly_stats(db, audiobook_id=args.book_id)
    
    if args.top:
        show_top_books(db, limit=args.limit, period=args.period)


if __name__ == '__main__':
    main()
