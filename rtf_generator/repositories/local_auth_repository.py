from werkzeug.security import check_password_hash, generate_password_hash

from database.local_connection import (
    TABLE_USER_CHART_STATUSES,
    TABLE_USER_KANBAN_COLUMN_ORDERS,
    TABLE_USER_KANBAN_STATUSES,
    TABLE_USER_SUBJECTS,
    TABLE_USER_DEPARTMENTS,
    TABLE_USERS,
    get_local_connection,
    init_local_db,
)
from utils.dashboard_statuses import (
    STATUS_BY_CODE,
    get_dashboard_status_definitions,
    get_default_dashboard_status_codes,
    get_default_kanban_status_codes,
    normalize_kanban_column_order,
    normalize_dashboard_status_codes,
)


class LocalAuthRepository:
    def __init__(self, db_path):
        self.db_path = db_path
        init_local_db(db_path)

    def _normalize_chart_flags(self, chart_flags=None):
        flags = chart_flags or {}
        return {
            "show_external": bool(flags.get("show_external", True)),
            "show_internal": bool(flags.get("show_internal", True)),
        }

    def _normalize_chart_status_codes(self, chart_status_codes=None):
        codes = normalize_dashboard_status_codes(chart_status_codes)
        return codes or get_default_dashboard_status_codes()

    def _normalize_kanban_status_codes(self, kanban_status_codes=None):
        codes = normalize_dashboard_status_codes(kanban_status_codes)
        return codes or get_default_kanban_status_codes()

    def list_available_chart_statuses(self):
        return get_dashboard_status_definitions()

    def list_available_kanban_statuses(self):
        return get_dashboard_status_definitions()

    def get_kanban_column_order_for_user(self, user_id, kanban_status_codes=None):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT column_id
            FROM {TABLE_USER_KANBAN_COLUMN_ORDERS}
            WHERE user_id = %s
            ORDER BY display_order ASC, column_id ASC
            """,
            (int(user_id),),
        )
        rows = cur.fetchall()
        conn.close()
        return normalize_kanban_column_order([row[0] for row in rows], kanban_status_codes)

    def count_users(self):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_USERS}")
        row = cur.fetchone()
        conn.close()
        return int(row[0] or 0)

    def list_users(self):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, username, display_name, profile, is_active, chart_show_external, chart_show_internal, last_login_at, created_at
            FROM {TABLE_USERS}
            ORDER BY LOWER(username)
            """
        )
        rows = cur.fetchall()
        conn.close()
        users = []
        for row in rows:
            users.append(
                {
                    "id": int(row[0]),
                    "username": row[1],
                    "display_name": row[2],
                    "profile": row[3],
                    "is_active": bool(row[4]),
                    "chart_show_external": bool(row[5]),
                    "chart_show_internal": bool(row[6]),
                    "last_login_at": row[7],
                    "created_at": row[8],
                }
            )
        return users

    def get_user_by_username(self, username):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, username, password_hash, display_name, profile, is_active, chart_show_external, chart_show_internal, last_login_at, created_at
            FROM {TABLE_USERS}
            WHERE LOWER(username) = LOWER(%s)
            LIMIT 1
            """,
            ((username or "").strip(),),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "username": row[1],
            "password_hash": row[2],
            "display_name": row[3],
            "profile": row[4],
            "is_active": bool(row[5]),
            "chart_show_external": bool(row[6]),
            "chart_show_internal": bool(row[7]),
            "last_login_at": row[8],
            "created_at": row[9],
        }

    def get_departments_for_user(self, user_id):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT cod_depar, COALESCE(nome_departamento, '')
            FROM {TABLE_USER_DEPARTMENTS}
            WHERE user_id = %s
            ORDER BY cod_depar
            """,
            (int(user_id),),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "cod_depar": int(row[0]),
                "nome_departamento": row[1] or "",
            }
            for row in rows
        ]

    def get_subjects_for_user(self, user_id):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT cod_assunto, COALESCE(descr_assunto, '')
            FROM {TABLE_USER_SUBJECTS}
            WHERE user_id = %s
            ORDER BY cod_assunto
            """,
            (int(user_id),),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "cod_assunto": int(row[0]),
                "descr_assunto": row[1] or "",
            }
            for row in rows
        ]

    def get_chart_statuses_for_user(self, user_id):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT status_code
            FROM {TABLE_USER_CHART_STATUSES}
            WHERE user_id = %s
            ORDER BY status_code
            """,
            (int(user_id),),
        )
        rows = cur.fetchall()
        conn.close()
        codes = normalize_dashboard_status_codes([row[0] for row in rows])
        if not codes:
            codes = get_default_dashboard_status_codes()
        return [
            {
                "code": code,
                "label": STATUS_BY_CODE[code]["label"],
                "chart_label": STATUS_BY_CODE[code]["chart_label"],
            }
            for code in codes
        ]

    def get_kanban_statuses_for_user(self, user_id):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT status_code
            FROM {TABLE_USER_KANBAN_STATUSES}
            WHERE user_id = %s
            ORDER BY status_code
            """,
            (int(user_id),),
        )
        rows = cur.fetchall()
        conn.close()
        codes = normalize_dashboard_status_codes([row[0] for row in rows])
        if not codes:
            codes = get_default_kanban_status_codes()
        return [
            {
                "code": code,
                "label": STATUS_BY_CODE[code]["label"],
                "chart_label": STATUS_BY_CODE[code]["chart_label"],
            }
            for code in codes
        ]

    def _derive_subjects_from_departments(self, user_id):
        departments = self.get_departments_for_user(user_id)
        if not departments:
            return []
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT DC1739.COD_ASSUNTO, COALESCE(DC1739.DESCR_ASSUNTO, '')
            FROM BANCO01.DC1966
            JOIN BANCO01.DC1739 ON (DC1739.COD_ASSUNTO = DC1966.COD_ASSUNTO)
            WHERE DC1966.COD_DEPAR = ANY(%s)
            ORDER BY DC1739.COD_ASSUNTO
            """,
            ([int(d["cod_depar"]) for d in departments],),
        )
        rows = cur.fetchall()
        conn.close()
        subjects = [
            {
                "cod_assunto": int(row[0]),
                "descr_assunto": row[1] or "",
            }
            for row in rows
        ]
        if subjects:
            self.replace_user_subjects(user_id, subjects)
        return subjects

    def replace_user_subjects(self, user_id, subjects):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE_USER_SUBJECTS} WHERE user_id = %s", (int(user_id),))
        for subject in subjects or []:
            cod_assunto = int(subject.get("cod_assunto"))
            descr_assunto = (subject.get("descr_assunto") or "").strip() or None
            cur.execute(
                f"""
                INSERT INTO {TABLE_USER_SUBJECTS} (user_id, cod_assunto, descr_assunto)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, cod_assunto) DO UPDATE SET
                    descr_assunto = EXCLUDED.descr_assunto
                """,
                (int(user_id), cod_assunto, descr_assunto),
            )
        conn.commit()
        conn.close()

    def replace_user_chart_statuses(self, user_id, chart_status_codes):
        codes = self._normalize_chart_status_codes(chart_status_codes)
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE_USER_CHART_STATUSES} WHERE user_id = %s", (int(user_id),))
        for code in codes:
            cur.execute(
                f"""
                INSERT INTO {TABLE_USER_CHART_STATUSES} (user_id, status_code)
                VALUES (%s, %s)
                ON CONFLICT (user_id, status_code) DO NOTHING
                """,
                (int(user_id), code),
            )
        conn.commit()
        conn.close()

    def replace_user_kanban_statuses(self, user_id, kanban_status_codes):
        codes = self._normalize_kanban_status_codes(kanban_status_codes)
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE_USER_KANBAN_STATUSES} WHERE user_id = %s", (int(user_id),))
        for code in codes:
            cur.execute(
                f"""
                INSERT INTO {TABLE_USER_KANBAN_STATUSES} (user_id, status_code)
                VALUES (%s, %s)
                ON CONFLICT (user_id, status_code) DO NOTHING
                """,
                (int(user_id), code),
            )
        conn.commit()
        conn.close()

    def replace_user_kanban_column_order(self, user_id, column_ids, kanban_status_codes=None):
        ordered_columns = normalize_kanban_column_order(column_ids, kanban_status_codes)
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE_USER_KANBAN_COLUMN_ORDERS} WHERE user_id = %s", (int(user_id),))
        for index, column_id in enumerate(ordered_columns, start=1):
            cur.execute(
                f"""
                INSERT INTO {TABLE_USER_KANBAN_COLUMN_ORDERS} (user_id, column_id, display_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, column_id) DO UPDATE SET
                    display_order = EXCLUDED.display_order
                """,
                (int(user_id), column_id, int(index)),
            )
        conn.commit()
        conn.close()

    def list_users_with_subjects(self):
        users = self.list_users()
        for user in users:
            user["subjects"] = self.get_subjects_for_user(user["id"])
            user["chart_statuses"] = self.get_chart_statuses_for_user(user["id"])
            user["chart_status_codes"] = [item["code"] for item in user["chart_statuses"]]
            user["kanban_statuses"] = self.get_kanban_statuses_for_user(user["id"])
            user["kanban_status_codes"] = [item["code"] for item in user["kanban_statuses"]]
            user["kanban_column_order"] = self.get_kanban_column_order_for_user(user["id"], user["kanban_status_codes"])
            if not user["subjects"]:
                user["subjects"] = self._derive_subjects_from_departments(user["id"])
        return users

    def list_available_subjects(self):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DC1739.COD_ASSUNTO, COALESCE(DC1739.DESCR_ASSUNTO, '')
            FROM BANCO01.DC1739
            WHERE (DC1739.DATA_DESAT = 0 OR DC1739.DATA_DESAT IS NULL)
            ORDER BY DC1739.DESCR_ASSUNTO
            """
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "cod_assunto": int(row[0]),
                "descr_assunto": row[1] or "",
            }
            for row in rows
        ]

    def update_user(self, user_id, display_name, profile="subject", is_active=True, password=None, subjects=None, chart_flags=None, chart_status_codes=None, kanban_status_codes=None):
        profile = (profile or "subject").strip().lower()
        if profile not in {"admin", "subject"}:
            raise ValueError("Perfil inválido")
        display_name = (display_name or "").strip()
        if not display_name:
            raise ValueError("Nome é obrigatório")
        chart_flags = self._normalize_chart_flags(chart_flags)

        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        if password:
            cur.execute(
                f"""
                UPDATE {TABLE_USERS}
                SET display_name = %s,
                    profile = %s,
                    is_active = %s,
                    chart_show_external = %s,
                    chart_show_internal = %s,
                    password_hash = %s
                WHERE id = %s
                """,
                (
                    display_name,
                    profile,
                    bool(is_active),
                    chart_flags["show_external"],
                    chart_flags["show_internal"],
                    generate_password_hash(password),
                    int(user_id),
                ),
            )
        else:
            cur.execute(
                f"""
                UPDATE {TABLE_USERS}
                SET display_name = %s,
                    profile = %s,
                    is_active = %s,
                    chart_show_external = %s,
                    chart_show_internal = %s
                WHERE id = %s
                """,
                (
                    display_name,
                    profile,
                    bool(is_active),
                    chart_flags["show_external"],
                    chart_flags["show_internal"],
                    int(user_id),
                ),
            )
        conn.commit()
        conn.close()

        self.replace_user_chart_statuses(user_id, chart_status_codes)
        self.replace_user_kanban_statuses(user_id, kanban_status_codes)
        self.replace_user_kanban_column_order(user_id, None, kanban_status_codes)
        if profile == "admin":
            self.replace_user_subjects(user_id, [])
        else:
            self.replace_user_subjects(user_id, subjects or [])

    def create_user(self, username, password, display_name, profile="subject", subjects=None, departments=None, is_active=True, chart_flags=None, chart_status_codes=None, kanban_status_codes=None):
        username = (username or "").strip()
        display_name = (display_name or "").strip()
        password = password or ""
        profile = (profile or "subject").strip().lower()
        subjects = subjects or []
        departments = departments or []
        chart_flags = self._normalize_chart_flags(chart_flags)
        if not username or not display_name or not password:
            raise ValueError("Usuário, nome e senha são obrigatórios")
        if profile not in {"admin", "department", "subject"}:
            raise ValueError("Perfil inválido")

        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            INSERT INTO {TABLE_USERS} (username, password_hash, display_name, profile, is_active, chart_show_external, chart_show_internal)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                username,
                generate_password_hash(password),
                display_name,
                profile,
                bool(is_active),
                chart_flags["show_external"],
                chart_flags["show_internal"],
            ),
        )
        user_id = int(cur.fetchone()[0])

        if subjects and profile != "admin":
            for subject in subjects:
                cod_assunto = int(subject.get("cod_assunto"))
                descr_assunto = (subject.get("descr_assunto") or "").strip() or None
                cur.execute(
                    f"""
                    INSERT INTO {TABLE_USER_SUBJECTS} (user_id, cod_assunto, descr_assunto)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, cod_assunto) DO UPDATE SET
                        descr_assunto = EXCLUDED.descr_assunto
                    """,
                    (user_id, cod_assunto, descr_assunto),
                )

        if departments and profile != "admin":
            for dep in departments:
                cod_depar = int(dep.get("cod_depar"))
                nome_departamento = (dep.get("nome_departamento") or "").strip() or None
                cur.execute(
                    f"""
                    INSERT INTO {TABLE_USER_DEPARTMENTS} (user_id, cod_depar, nome_departamento)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, cod_depar) DO UPDATE SET
                        nome_departamento = EXCLUDED.nome_departamento
                    """,
                    (user_id, cod_depar, nome_departamento),
                )

        conn.commit()
        conn.close()
        self.replace_user_chart_statuses(user_id, chart_status_codes)
        self.replace_user_kanban_statuses(user_id, kanban_status_codes)
        self.replace_user_kanban_column_order(user_id, None, kanban_status_codes)
        return user_id

    def authenticate(self, username, password):
        user = self.get_user_by_username(username)
        if not user or not user.get("is_active"):
            return None
        if not check_password_hash(user["password_hash"], password or ""):
            return None
        self.touch_last_login(user["id"])
        return self.get_user_with_subjects(user["id"])

    def get_user_with_subjects(self, user_id):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, username, display_name, profile, is_active, chart_show_external, chart_show_internal, last_login_at, created_at
            FROM {TABLE_USERS}
            WHERE id = %s
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        user = {
            "id": int(row[0]),
            "username": row[1],
            "display_name": row[2],
            "profile": row[3],
            "is_active": bool(row[4]),
            "chart_show_external": bool(row[5]),
            "chart_show_internal": bool(row[6]),
            "last_login_at": row[7],
            "created_at": row[8],
        }
        user["chart_statuses"] = self.get_chart_statuses_for_user(user["id"])
        user["chart_status_codes"] = [item["code"] for item in user["chart_statuses"]]
        user["kanban_statuses"] = self.get_kanban_statuses_for_user(user["id"])
        user["kanban_status_codes"] = [item["code"] for item in user["kanban_statuses"]]
        user["kanban_column_order"] = self.get_kanban_column_order_for_user(user["id"], user["kanban_status_codes"])
        user["subjects"] = self.get_subjects_for_user(user["id"])
        if not user["subjects"]:
            user["subjects"] = self._derive_subjects_from_departments(user["id"])
        return user

    def touch_last_login(self, user_id):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE {TABLE_USERS}
            SET last_login_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (int(user_id),),
        )
        conn.commit()
        conn.close()
