from datetime import datetime

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
