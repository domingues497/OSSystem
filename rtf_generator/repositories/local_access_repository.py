from datetime import datetime
from database.local_connection import TABLE_ACCESS_DAILY, get_local_connection


class LocalAccessRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def track(self, ip, path, user_agent=""):
        ip = (ip or "").strip()
        if not ip:
            return
        day_erp = int(datetime.now().strftime("%Y%m%d"))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO {table} (day_erp, ip, count, first_seen, last_seen, last_path, user_agent)
            VALUES (%s, %s, 1, %s, %s, %s, %s)
            ON CONFLICT(day_erp, ip) DO UPDATE SET
                count = count + 1,
                last_seen = EXCLUDED.last_seen,
                last_path = EXCLUDED.last_path,
                user_agent = EXCLUDED.user_agent
            """.format(table=TABLE_ACCESS_DAILY),
            (day_erp, ip, now_str, now_str, (path or "")[:500], (user_agent or "")[:400]),
        )
        conn.commit()
        conn.close()

    def get_day(self, day_erp):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ip, count, first_seen, last_seen, last_path
            FROM {table}
            WHERE day_erp = %s
            ORDER BY count DESC, ip ASC
            """.format(table=TABLE_ACCESS_DAILY),
            (int(day_erp),),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "ip": r[0],
                "count": int(r[1] or 0),
                "first_seen": r[2],
                "last_seen": r[3],
                "last_path": r[4],
            }
            for r in rows
        ]
