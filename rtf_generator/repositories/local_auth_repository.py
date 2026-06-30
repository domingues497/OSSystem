from werkzeug.security import check_password_hash, generate_password_hash

from database.local_connection import (
    TABLE_USER_SUBJECTS,
    TABLE_USER_DEPARTMENTS,
    TABLE_USERS,
    get_local_connection,
    init_local_db,
)


class LocalAuthRepository:
    def __init__(self, db_path):
        self.db_path = db_path
        init_local_db(db_path)

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
            SELECT id, username, display_name, profile, is_active, last_login_at, created_at
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
                    "last_login_at": row[5],
                    "created_at": row[6],
                }
            )
        return users

    def get_user_by_username(self, username):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, username, password_hash, display_name, profile, is_active, last_login_at, created_at
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
            "last_login_at": row[6],
            "created_at": row[7],
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

    def list_users_with_subjects(self):
        users = self.list_users()
        for user in users:
            user["subjects"] = self.get_subjects_for_user(user["id"])
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

    def update_user(self, user_id, display_name, profile="subject", is_active=True, password=None, subjects=None):
        profile = (profile or "subject").strip().lower()
        if profile not in {"admin", "subject"}:
            raise ValueError("Perfil inválido")
        display_name = (display_name or "").strip()
        if not display_name:
            raise ValueError("Nome é obrigatório")

        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        if password:
            cur.execute(
                f"""
                UPDATE {TABLE_USERS}
                SET display_name = %s,
                    profile = %s,
                    is_active = %s,
                    password_hash = %s
                WHERE id = %s
                """,
                (display_name, profile, bool(is_active), generate_password_hash(password), int(user_id)),
            )
        else:
            cur.execute(
                f"""
                UPDATE {TABLE_USERS}
                SET display_name = %s,
                    profile = %s,
                    is_active = %s
                WHERE id = %s
                """,
                (display_name, profile, bool(is_active), int(user_id)),
            )
        conn.commit()
        conn.close()

        if profile == "admin":
            self.replace_user_subjects(user_id, [])
        else:
            self.replace_user_subjects(user_id, subjects or [])

    def create_user(self, username, password, display_name, profile="subject", subjects=None, departments=None, is_active=True):
        username = (username or "").strip()
        display_name = (display_name or "").strip()
        password = password or ""
        profile = (profile or "subject").strip().lower()
        subjects = subjects or []
        departments = departments or []
        if not username or not display_name or not password:
            raise ValueError("Usuário, nome e senha são obrigatórios")
        if profile not in {"admin", "department", "subject"}:
            raise ValueError("Perfil inválido")

        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            INSERT INTO {TABLE_USERS} (username, password_hash, display_name, profile, is_active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (username, generate_password_hash(password), display_name, profile, bool(is_active)),
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
            SELECT id, username, display_name, profile, is_active, last_login_at, created_at
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
            "last_login_at": row[5],
            "created_at": row[6],
        }
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
