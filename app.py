import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import json
import os

# ---------- Конфигурация страницы ----------
st.set_page_config(
    page_title="Сравнение вузов",
    page_icon="🎓",
    layout="wide",
)

# --- НАСТРОЙКА ПОДКЛЮЧЕНИЯ К GOOGLE SHEETS ---
# Streamlit автоматически подхватит настройки из secrets.toml
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------- Работа с данными ----------
def default_data():
    return {
        "columns": [
            {"name": "Название",        "type": "text"},
            {"name": "Бюджетные места", "type": "number"},
            {"name": "Общежитие",       "type": "text"},
            {"name": "Время в пути",    "type": "number"},
        ],
        "rows": [
            {"id": 1, "values": {"Название": "МГУ", "Бюджетные места": 4000, "Общежитие": "Да", "Время в пути": 60}},
            {"id": 2, "values": {"Название": "МФТИ", "Бюджетные места": 1200, "Общежитие": "Да", "Время в пути": 90}},
            {"id": 3, "values": {"Название": "ВШЭ", "Бюджетные места": 3500, "Общежитие": "Нет", "Время в пути": 45}},
        ],
        "next_id": 4,
        "sort": {"column": None, "direction": 0},
    }

def load_data():
    try:
        # Читаем данные из Google Sheets
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        # Если таблица пустая, возвращаем дефолтные данные
        if df.empty or 'id' not in df.columns:
            return default_data()
        
        data = default_data()
        data['next_id'] = int(df['id'].max()) + 1 if not df.empty else 1
        data['rows'] = []
        
        for _, row in df.iterrows():
            row_dict = {"id": int(row['id']), "values": {}}
            for col in data['columns']:
                col_name = col['name']
                if col_name in df.columns:
                    val = row[col_name]
                    row_dict['values'][col_name] = val if pd.notna(val) else ""
            data['rows'].append(row_dict)
        return data
    except Exception as e:
        st.warning(f"Не удалось загрузить данные из Google Sheets. Используются локальные. Ошибка: {e}")
        # Если облако недоступно, грузим локальный файл (если есть)
        if os.path.exists("data.json"):
            with open("data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return default_data()

def save_data(data):
    # Сохраняем локально как резервную копию
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    try:
        # Сохраняем в Google Sheets
        rows_list = []
        for row in data['rows']:
            flat_row = {"id": row["id"]}
            flat_row.update(row["values"])
            rows_list.append(flat_row)
        
        df = pd.DataFrame(rows_list)
        if not df.empty:
            conn.update(worksheet="Sheet1", data=df)
            st.toast("Данные сохранены в облако", icon="✅")
    except Exception as e:
        st.error(f"Ошибка сохранения в Google Sheets: {e}")

# ---------- Инициализация состояния ----------
if "data" not in st.session_state:
    st.session_state.data = load_data()

data = st.session_state.data

# ---------- Определение мобильного устройства ----------
def is_mobile():
    try:
        headers = st.context.headers
        ua = headers.get("User-Agent", "").lower()
        mobile_markers = ["iphone", "android", "mobile", "ipad", "tablet"]
        return any(m in ua for m in mobile_markers)
    except Exception:
        return False

MOBILE = is_mobile()

# ---------- Вспомогательные функции ----------
def add_row():
    new_id = data["next_id"]
    data["next_id"] += 1
    row = {"id": new_id, "values": {}}
    for col in data["columns"]:
        row["values"][col["name"]] = "" if col["type"] == "text" else (0 if col["type"] == "number" else 5)
    data["rows"].append(row)
    save_data(data)

def delete_row(row_id):
    data["rows"] = [r for r in data["rows"] if r["id"] != row_id]
    save_data(data)

def add_column(name, col_type):
    if any(c["name"] == name for c in data["columns"]):
        st.warning("Колонка с таким названием уже существует")
        return
    data["columns"].append({"name": name, "type": col_type})
    for row in data["rows"]:
        row["values"][name] = "" if col_type == "text" else (0 if col_type == "number" else 5)
    save_data(data)

def delete_column(name):
    data["columns"] = [c for c in data["columns"] if c["name"] != name]
    for row in data["rows"]:
        row["values"].pop(name, None)
    if data["sort"]["column"] == name:
        data["sort"] = {"column": None, "direction": 0}
    save_data(data)

def sort_key(value, col_type):
    if value is None or value == "":
        return (1, "")
    if col_type == "number":
        try:
            return (0, float(value))
        except (ValueError, TypeError):
            return (1, str(value))
    return (0, str(value).lower())

def get_sorted_rows():
    rows = list(data["rows"])
    col = data["sort"]["column"]
    direction = data["sort"]["direction"]
    if col and direction in (1, 2):
        col_type = next((c["type"] for c in data["columns"] if c["name"] == col), "text")
        rows.sort(key=lambda r: sort_key(r["values"].get(col, ""), col_type),
                  reverse=(direction == 2))
    return rows

def click_header(col_name):
    s = data["sort"]
    if s["column"] != col_name:
        s["column"] = col_name
        s["direction"] = 1
    else:
        s["direction"] = (s["direction"] + 1) % 3
        if s["direction"] == 0:
            s["column"] = None
    save_data(data)

# ---------- UI ----------
if MOBILE:
    st.markdown("### 🎓 Сравнение вузов (режим просмотра)")
    st.caption("Мобильная версия: только просмотр и сортировка")
else:
    st.markdown("## 🎓 Сравнение вузов")

    with st.expander("➕ Добавить вуз / колонку / управление", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Добавить вуз**")
            if st.button("➕ Добавить вуз", use_container_width=True):
                add_row()
                st.rerun()

        with col2:
            st.markdown("**Добавить колонку (признак)**")
            new_col_name = st.text_input("Название колонки", key="new_col_name")
            new_col_type = st.selectbox(
                "Тип данных",
                options=["text", "number", "rating"],
                format_func=lambda x: {"text": "Текст", "number": "Число", "rating": "Рейтинг 1-10"}[x],
                key="new_col_type",
            )
            if st.button("➕ Добавить колонку", use_container_width=True):
                if not new_col_name.strip():
                    st.warning("Введите название колонки")
                else:
                    add_column(new_col_name.strip(), new_col_type)
                    st.rerun()

# ---------- Заголовок таблицы ----------
st.markdown("---")

columns = data["columns"]
sort_info = data["sort"]

header_cols = st.columns(len(columns) + (1 if not MOBILE else 0))

for i, col in enumerate(columns):
    marker = ""
    if sort_info["column"] == col["name"]:
        marker = " ▲" if sort_info["direction"] == 1 else (" ▼" if sort_info["direction"] == 2 else "")
    with header_cols[i]:
        label = f"**{col['name']}{marker}**"
        if st.button(label, key=f"sort_{col['name']}", use_container_width=True):
            click_header(col["name"])
            st.rerun()

if not MOBILE:
    with header_cols[-1]:
        st.markdown("**Действия**")

# ---------- Тело таблицы ----------
sorted_rows = get_sorted_rows()

if MOBILE:
    # --- МОБИЛЬНАЯ ВЕРСИЯ (КРАСИВАЯ ТАБЛИЦА) ---
    # Формируем HTML-таблицу с горизонтальной прокруткой
    html = '<div style="overflow-x: auto; -webkit-overflow-scrolling: touch;">'
    html += '<table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif;">'
    
    # Заголовки таблицы
    html += '<thead><tr style="background-color: #f0f2f6; border-bottom: 2px solid #ddd;">'
    for col in columns:
        marker = ""
        if sort_info["column"] == col["name"]:
            marker = " ▲" if sort_info["direction"] == 1 else (" ▼" if sort_info["direction"] == 2 else "")
        html += f'<th style="padding: 10px; white-space: nowrap; border-right: 1px solid #ddd;">{col["name"]}{marker}</th>'
    html += '</tr></thead><tbody>'
    
    # Строки таблицы
    for row in sorted_rows:
        html += '<tr style="border-bottom: 1px solid #eee;">'
        for col in columns:
            val = row["values"].get(col["name"], "")
            html += f'<td style="padding: 10px; white-space: nowrap; border-right: 1px solid #eee;">{val}</td>'
        html += '</tr>'
    
    html += '</tbody></table></div>'
    
    # Выводим на экран
    st.markdown(html, unsafe_allow_html=True)
    
    # Кнопки сортировки под таблицей (чтобы на телефоне было удобно нажимать)
    st.markdown("<br>**Сортировать по:**", unsafe_allow_html=True)
    cols = st.columns(2)
    for i, col in enumerate(columns):
        with cols[i % 2]:
            marker = ""
            if sort_info["column"] == col["name"]:
                marker = " ▲" if sort_info["direction"] == 1 else (" ▼" if sort_info["direction"] == 2 else "")
            if st.button(f"{col['name']}{marker}", key=f"mob_sort_{col['name']}", use_container_width=True):
                click_header(col["name"])
                st.rerun()

else:
    # --- ДЕСКТОПНАЯ ВЕРСИЯ (РЕДАКТИРУЕМАЯ) ---
    # Заголовок таблицы
    header_cols = st.columns(len(columns) + 1)
    for i, col in enumerate(columns):
        marker = ""
        if sort_info["column"] == col["name"]:
            marker = " ▲" if sort_info["direction"] == 1 else (" ▼" if sort_info["direction"] == 2 else "")
        with header_cols[i]:
            label = f"**{col['name']}{marker}**"
            if st.button(label, key=f"sort_{col['name']}", use_container_width=True):
                click_header(col["name"])
                st.rerun()
    with header_cols[-1]:
        st.markdown("**Действия**")

    for row in sorted_rows:
        row_cols = st.columns(len(columns) + 1)
        for i, col in enumerate(columns):
            val = row["values"].get(col["name"], "")
            with row_cols[i]:
                key = f"cell_{row['id']}_{col['name']}"
                if col["type"] == "text":
                    new_val = st.text_input("", value=str(val), key=key, label_visibility="collapsed")
                elif col["type"] == "number":
                    try:
                        num_val = float(val) if val not in (None, "") else 0.0
                    except (ValueError, TypeError):
                        num_val = 0.0
                    new_val = st.number_input("", value=num_val, key=key, label_visibility="collapsed")
                else:  # rating
                    try:
                        rating_val = int(val) if val not in (None, "") else 5
                    except (ValueError, TypeError):
                        rating_val = 5
                    rating_val = max(1, min(10, rating_val))
                    new_val = st.slider("", 1, 10, rating_val, key=key, label_visibility="collapsed")
                
                if new_val != val:
                    row["values"][col["name"]] = new_val
                    save_data(data)
        with row_cols[-1]:
            if st.button("🗑️", key=f"del_{row['id']}", help="Удалить вуз"):
                delete_row(row["id"])
                st.rerun()

# ---------- Управление колонками (только ПК) ----------
if not MOBILE:
    with st.expander("⚙️ Удалить колонку"):
        col_to_delete = st.selectbox(
            "Выберите колонку для удаления",
            options=[c["name"] for c in columns],
            key="del_col",
        )
        if st.button("Удалить колонку", type="secondary"):
            delete_column(col_to_delete)
            st.rerun()

    st.markdown("---")
    if st.button("🔄 Сбросить сортировку"):
        data["sort"] = {"column": None, "direction": 0}
        save_data(data)
        st.rerun()

    st.caption(f"Всего вузов: {len(data['rows'])} | Колонок: {len(columns)} | "
               f"Активная сортировка: {sort_info['column'] or '—'}")
