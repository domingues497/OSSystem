from datetime import datetime
from datetime import timedelta

def format_erp_date(date_val):
    if not date_val: return ""
    try:
        s = str(int(date_val))
        if len(s) == 8:
            return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"
        return s
    except:
        return str(date_val)

def format_erp_time(time_val):
    if time_val is None: return ""
    try:
        s_time = str(time_val)
        if '.' in s_time:
            parts = s_time.split('.')
            hh = parts[0].zfill(2)
            mmss = parts[1].ljust(4, '0')[:4]
            s = hh + mmss
        else:
            s = s_time.zfill(6)
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"
    except:
        return str(time_val)

def erp_to_datetime(date_val, time_val):
    try:
        if not date_val: return None
        d_str = str(int(date_val)).zfill(8)
        
        if time_val is None:
            t_str = "000000"
        else:
            s_time = str(time_val)
            if '.' in s_time:
                parts = s_time.split('.')
                hh = parts[0].zfill(2)
                mmss = parts[1].ljust(4, '0')[:4]
                t_str = hh + mmss
            else:
                t_str = s_time.zfill(6)
        
        return datetime.strptime(f"{d_str}{t_str[:6]}", "%Y%m%d%H%M%S")
    except:
        return None

def format_duration(td):
    if not td: return ""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0 or not parts: parts.append(f"{minutes}m")
    return " ".join(parts)

def format_duration_short(td_or_seconds):
    if not td_or_seconds: return "0m"
    
    # Se for timedelta, extrair segundos
    if hasattr(td_or_seconds, 'total_seconds'):
        seconds = td_or_seconds.total_seconds()
    else:
        seconds = td_or_seconds
        
    if seconds < 0: return "0m"
    
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0: return f"{days}d {hours}h"
    if hours > 0: return f"{hours}h {minutes}m"
    return f"{minutes}m"

def _work_windows_minutes(d: datetime):
    dow = d.weekday()
    if dow >= 5:
        return []
    if dow == 4:
        return [(7 * 60 + 30, 12 * 60), (13 * 60, 17 * 60)]
    return [(7 * 60 + 30, 12 * 60), (13 * 60, 18 * 60)]

def add_business_minutes(start_dt: datetime, minutes: int):
    if start_dt is None:
        return None
    if minutes <= 0:
        return start_dt
    cursor = start_dt.replace(microsecond=0)
    remaining = int(minutes)
    while remaining > 0:
        windows = _work_windows_minutes(cursor)
        if not windows:
            cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            continue
        cur_min = cursor.hour * 60 + cursor.minute
        active = None
        next_start = None
        for w_start, w_end in windows:
            if cur_min < w_start:
                next_start = w_start
                break
            if w_start <= cur_min < w_end:
                active = (w_start, w_end)
                break
        if active is None:
            if next_start is not None:
                cursor = cursor.replace(hour=next_start // 60, minute=next_start % 60, second=0, microsecond=0)
                continue
            cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            continue
        _, w_end = active
        window_end_dt = cursor.replace(hour=w_end // 60, minute=w_end % 60, second=0, microsecond=0)
        window_remaining = int((window_end_dt - cursor).total_seconds() // 60)
        if window_remaining <= 0:
            cursor = window_end_dt
            continue
        take = min(remaining, window_remaining)
        cursor = cursor + timedelta(minutes=take)
        remaining -= take
    return cursor

def business_minutes_between(start_dt: datetime, end_dt: datetime):
    if start_dt is None or end_dt is None:
        return 0
    if end_dt <= start_dt:
        return 0
    start = start_dt.replace(microsecond=0)
    end = end_dt.replace(microsecond=0)
    total = 0
    cursor = start
    while cursor.date() <= end.date():
        day_start = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        segment_start = max(cursor, day_start)
        segment_end = min(end, day_end)
        windows = _work_windows_minutes(segment_start)
        for w_start, w_end in windows:
            w_start_dt = day_start.replace(hour=w_start // 60, minute=w_start % 60)
            w_end_dt = day_start.replace(hour=w_end // 60, minute=w_end % 60)
            a = max(segment_start, w_start_dt)
            b = min(segment_end, w_end_dt)
            if b > a:
                total += int((b - a).total_seconds() // 60)
        cursor = day_end
    return total
