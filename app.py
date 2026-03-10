import os
import shutil
import sqlite3
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import font as tkfont
from PIL import Image, ImageTk

DB_PATH = "store.db"
RES_DIR = "resources"
PLACEHOLDER = os.path.join(RES_DIR, "picture.png")

DISCOUNT_BG = "#2E8B57"
OUT_OF_STOCK_BG = "#ADD8E6"


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def authenticate(login, password):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        """
    SELECT users.full_name, roles.name
    FROM users
    JOIN roles ON users.role_id = roles.id
    WHERE TRIM(login)=? AND TRIM(password)=?
    """,
        (login.strip(), password.strip()),
    )
    result = cursor.fetchone()
    conn.close()
    return result


def safe_image_path(photo_filename):
    if photo_filename is None:
        return PLACEHOLDER
    s = str(photo_filename).strip()
    if s == "" or s.lower() == "nan":
        return PLACEHOLDER
    candidate = os.path.join(RES_DIR, s)
    return candidate if os.path.exists(candidate) else PLACEHOLDER


def discounted_price(price: float, discount_percent: float) -> float:
    return round(price * (1 - discount_percent / 100.0), 2)


def fetch_suppliers():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM suppliers ORDER BY name")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def fetch_categories():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories ORDER BY name")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def fetch_manufacturers():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM manufacturers ORDER BY name")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def get_or_create_id(conn, table, name):
    cur = conn.cursor()
    cur.execute(f"INSERT OR IGNORE INTO {table}(name) VALUES (?)", (name,))
    cur.execute(f"SELECT id FROM {table} WHERE name=?", (name,))
    return cur.fetchone()[0]


def fetch_products(search_text="", supplier_filter="ALL", sort_mode="NONE"):
    search_text = (search_text or "").strip()
    supplier_filter = supplier_filter or "ALL"
    sort_mode = sort_mode or "NONE"

    conn = db_connect()
    cur = conn.cursor()

    base_sql = """
    SELECT
        p.id,
        p.article,
        p.name,
        p.unit,
        p.price,
        p.quantity,
        p.discount_percent,
        p.photo_filename,
        p.description,
        c.name AS category,
        m.name AS manufacturer,
        s.name AS supplier
    FROM products p
    JOIN categories c ON c.id = p.category_id
    JOIN manufacturers m ON m.id = p.manufacturer_id
    JOIN suppliers s ON s.id = p.supplier_id
    WHERE 1=1
    """

    params = []

    if supplier_filter != "ALL":
        base_sql += " AND s.name = ?"
        params.append(supplier_filter)

    if search_text != "":
        base_sql += """
        AND (
            LOWER(p.name) LIKE ?
            OR LOWER(c.name) LIKE ?
            OR LOWER(m.name) LIKE ?
            OR LOWER(s.name) LIKE ?
            OR LOWER(IFNULL(p.description,'')) LIKE ?
            OR LOWER(IFNULL(p.article,'')) LIKE ?
        )
        """
        like = f"%{search_text.lower()}%"
        params.extend([like, like, like, like, like, like])

    if sort_mode == "QTY_ASC":
        base_sql += " ORDER BY p.quantity ASC"
    elif sort_mode == "QTY_DESC":
        base_sql += " ORDER BY p.quantity DESC"
    else:
        base_sql += " ORDER BY p.id ASC"

    cur.execute(base_sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


class ProductForm(tk.Toplevel):
    def __init__(self, parent, app, mode="add", product_row=None):
        super().__init__(parent)
        self.app = app
        self.mode = mode  # "add" or "edit"
        self.product_row = product_row
        self.selected_image_path = None  # local file chosen by user

        self.title("Добавить товар" if mode == "add" else "Редактировать товар")
        self.geometry("520x520")

        self.base_font = tkfont.Font(family="Times New Roman", size=12)

        form = tk.Frame(self, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        def add_row(label, row_idx):
            tk.Label(form, text=label, font=self.base_font).grid(
                row=row_idx, column=0, sticky="w", pady=4
            )
            e = tk.Entry(form, width=35)
            e.grid(row=row_idx, column=1, sticky="w", pady=4)
            return e

        self.e_article = add_row("Артикул:", 0)
        self.e_name = add_row("Название:", 1)
        self.e_unit = add_row("Ед. изм.:", 2)
        self.e_price = add_row("Цена:", 3)
        self.e_qty = add_row("Кол-во:", 4)
        self.e_discount = add_row("Скидка %:", 5)

        tk.Label(form, text="Категория:", font=self.base_font).grid(
            row=6, column=0, sticky="w", pady=4
        )
        self.category_var = tk.StringVar()
        categories = fetch_categories()
        self.category_menu = tk.OptionMenu(form, self.category_var, *categories)
        self.category_menu.grid(row=6, column=1, sticky="w", pady=4)

        tk.Label(form, text="Производитель:", font=self.base_font).grid(
            row=7, column=0, sticky="w", pady=4
        )
        self.manufacturer_var = tk.StringVar()
        manufacturers = fetch_manufacturers()
        self.manufacturer_menu = tk.OptionMenu(
            form, self.manufacturer_var, *manufacturers
        )
        self.manufacturer_menu.grid(row=7, column=1, sticky="w", pady=4)

        tk.Label(form, text="Поставщик:", font=self.base_font).grid(
            row=8, column=0, sticky="w", pady=4
        )
        self.supplier_var = tk.StringVar()
        suppliers = fetch_suppliers()
        self.supplier_menu = tk.OptionMenu(form, self.supplier_var, *suppliers)
        self.supplier_menu.grid(row=8, column=1, sticky="w", pady=4)

        tk.Label(form, text="Описание:", font=self.base_font).grid(
            row=9, column=0, sticky="nw", pady=4
        )
        self.t_desc = tk.Text(form, width=35, height=5)
        self.t_desc.grid(row=9, column=1, sticky="w", pady=4)

        self.photo_label = tk.Label(
            form, text="Фото: (не выбрано)", font=self.base_font
        )
        self.photo_label.grid(row=10, column=0, columnspan=2, sticky="w", pady=6)

        btn_choose = tk.Button(form, text="Выбрать фото", command=self.choose_photo)
        btn_choose.grid(row=11, column=0, sticky="w", pady=6)

        btn_save = tk.Button(form, text="Сохранить", command=self.save)
        btn_save.grid(row=11, column=1, sticky="e", pady=6)

        # Fill data if edit
        if self.mode == "edit" and self.product_row:
            # row: id, article, name, unit, price, qty, disc, photo_filename, desc, category, manufacturer, supplier
            (
                _,
                article,
                name,
                unit,
                price,
                qty,
                disc,
                photo_filename,
                desc,
                category,
                manufacturer,
                supplier,
            ) = self.product_row
            self.e_article.insert(0, str(article))
            self.e_name.insert(0, str(name))
            self.e_unit.insert(0, str(unit or ""))
            self.e_price.insert(0, str(price))
            self.e_qty.insert(0, str(qty))
            self.e_discount.insert(0, str(disc))
            self.category_var.set(category)
            self.manufacturer_var.set(manufacturer)
            self.supplier_var.set(supplier)
            self.t_desc.insert("1.0", str(desc or ""))
            if photo_filename and str(photo_filename).strip() not in ("", "nan"):
                self.photo_label.config(text=f"Фото: {photo_filename}")

    def choose_photo(self):
        file_path = filedialog.askopenfilename(
            title="Выберите изображение", filetypes=[("Images", "*.png *.jpg *.jpeg")]
        )
        if file_path:
            self.selected_image_path = file_path
            self.photo_label.config(text=f"Фото: {os.path.basename(file_path)}")

    def save(self):
        article = self.e_article.get().strip()
        name = self.e_name.get().strip()
        unit = self.e_unit.get().strip()
        price = self.e_price.get().strip()
        qty = self.e_qty.get().strip()
        discount = self.e_discount.get().strip()

        category = self.category_var.get().strip()
        manufacturer = self.manufacturer_var.get().strip()
        supplier = self.supplier_var.get().strip()
        desc = self.t_desc.get("1.0", "end").strip()

        if (
            not article
            or not name
            or not price
            or not qty
            or not category
            or not manufacturer
            or not supplier
        ):
            messagebox.showerror(
                "Ошибка",
                "Заполните обязательные поля: Артикул, Название, Цена, Кол-во, Категория, Производитель, Поставщик",
            )
            return

        try:
            price_f = float(price)
            qty_i = int(qty)
            disc_f = float(discount) if discount else 0.0
        except:
            messagebox.showerror(
                "Ошибка", "Проверьте: Цена (число), Кол-во (целое), Скидка (число)"
            )
            return

        conn = db_connect()

        # get ids (create if not exist)
        category_id = get_or_create_id(conn, "categories", category)
        manufacturer_id = get_or_create_id(conn, "manufacturers", manufacturer)
        supplier_id = get_or_create_id(conn, "suppliers", supplier)

        # handle image copy
        photo_filename = None
        if self.selected_image_path:
            os.makedirs(RES_DIR, exist_ok=True)
            ext = os.path.splitext(self.selected_image_path)[1].lower()
            safe_name = f"{article}{ext}"
            dest = os.path.join(RES_DIR, safe_name)
            shutil.copyfile(self.selected_image_path, dest)
            photo_filename = safe_name

        cur = conn.cursor()

        try:
            if self.mode == "add":
                cur.execute(
                    """
                INSERT INTO products(
                    article, name, unit, price,
                    supplier_id, manufacturer_id, category_id,
                    discount_percent, quantity, description,
                    photo_filename, image_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                    (
                        article,
                        name,
                        unit,
                        price_f,
                        supplier_id,
                        manufacturer_id,
                        category_id,
                        disc_f,
                        qty_i,
                        desc,
                        photo_filename,
                        (f"{RES_DIR}/{photo_filename}" if photo_filename else None),
                    ),
                )
            else:
                # update
                product_id = self.product_row[0]

                old_photo = self.product_row[7]  # photo_filename القديم من DB

                # إذا لم نختر صورة جديدة: احتفظ بالقديمة
                if not photo_filename:
                    photo_filename = old_photo
                else:
                    # اخترنا صورة جديدة -> احذف القديمة من resources (إذا كانت موجودة)
                    if old_photo:
                        old_path = os.path.join(RES_DIR, old_photo)
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except:
                                pass

                cur.execute(
                    """
                UPDATE products
                SET article=?,
                    name=?,
                    unit=?,
                    price=?,
                    supplier_id=?,
                    manufacturer_id=?,
                    category_id=?,
                    discount_percent=?,
                    quantity=?,
                    description=?,
                    photo_filename=?,
                    image_path=?
                WHERE id=?
                """,
                    (
                        article,
                        name,
                        unit,
                        price_f,
                        supplier_id,
                        manufacturer_id,
                        category_id,
                        disc_f,
                        qty_i,
                        desc,
                        photo_filename,
                        (f"{RES_DIR}/{photo_filename}" if photo_filename else None),
                        product_id,
                    ),
                )

            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            conn.close()
            messagebox.showerror(
                "Ошибка", "Артикул должен быть уникальным (возможно уже существует)."
            )
            return

        self.app.refresh()
        self.destroy()


class ProductsUI:
    def __init__(self, user_name, role):
        self.user_name = user_name
        self.role = role

        self.window = tk.Toplevel()
        self.window.title("Товары")
        self.window.geometry("1100x650")

        # state: selected product (for edit/delete)
        self.selected_product_row = None

        self.base_font = tkfont.Font(family="Times New Roman", size=12)
        self.title_font = tkfont.Font(family="Times New Roman", size=13, weight="bold")
        self.old_price_font = tkfont.Font(family="Times New Roman", size=12)
        self.old_price_font.configure(overstrike=1)

        header = tk.Label(
            self.window,
            text=f"Пользователь: {self.user_name} ({self.role})",
            font=("Times New Roman", 14),
        )
        header.pack(pady=8)

        # Top bar
        self.topbar = tk.Frame(self.window, padx=10, pady=8)
        self.topbar.pack(fill="x")
        self.count_label = tk.Label(self.window, text="", font=("Times New Roman", 12))
        self.count_label.pack(anchor="w", padx=12)

        tk.Label(self.topbar, text="Поиск:", font=self.base_font).pack(side="left")
        self.search_var = tk.StringVar()
        tk.Entry(self.topbar, textvariable=self.search_var, width=30).pack(
            side="left", padx=8
        )

        tk.Label(self.topbar, text="Поставщик:", font=self.base_font).pack(
            side="left", padx=(15, 0)
        )
        self.supplier_var = tk.StringVar(value="ALL")
        suppliers = ["ALL"] + fetch_suppliers()
        tk.OptionMenu(self.topbar, self.supplier_var, *suppliers).pack(
            side="left", padx=8
        )

        tk.Label(self.topbar, text="Сортировка по складу:", font=self.base_font).pack(
            side="left", padx=(15, 0)
        )

        self.sort_var = tk.StringVar(value="NONE")
        self.sort_display = tk.StringVar(value="Нет")

        def set_sort(display_value):
            mapping = {
                "Нет": "NONE",
                "По возрастанию": "QTY_ASC",
                "По убыванию": "QTY_DESC",
            }
            self.sort_var.set(mapping.get(display_value, "NONE"))

        tk.OptionMenu(
            self.topbar,
            self.sort_display,
            "Нет",
            "По возрастанию",
            "По убыванию",
            command=set_sort,
        ).pack(side="left", padx=8)

        # Admin buttons (CRUD) — only for admin
        if self.role == "admin":
            btns = tk.Frame(self.window, padx=10, pady=6)
            btns.pack(fill="x")

            tk.Button(btns, text="➕ Добавить товар", command=self.add_product).pack(
                side="left"
            )
            tk.Button(btns, text="✏️ Редактировать", command=self.edit_product).pack(
                side="left", padx=8
            )
            tk.Button(btns, text="🗑️ Удалить", command=self.delete_product).pack(
                side="left"
            )

            hint = tk.Label(
                btns,
                text="(Чтобы выбрать товар: кликните по карточке)",
                font=("Times New Roman", 11),
            )
            hint.pack(side="right")

        # Scroll area
        self.canvas = tk.Canvas(self.window)
        self.scrollbar = tk.Scrollbar(
            self.window, orient="vertical", command=self.canvas.yview
        )
        self.scroll_frame = tk.Frame(self.canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # realtime
        self.search_var.trace_add("write", lambda *_: self.refresh())
        self.supplier_var.trace_add("write", lambda *_: self.refresh())
        self.sort_var.trace_add("write", lambda *_: self.refresh())

        self.refresh()

    def clear_list(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

    def refresh(self):
        self.selected_product_row = None
        self.clear_list()

        products = fetch_products(
            search_text=self.search_var.get(),
            supplier_filter=self.supplier_var.get(),
            sort_mode=self.sort_var.get(),
        )
        self.count_label.config(text=f"Найдено товаров: {len(products)}")

        for row in products:
            # row: id, article, name, unit, price, qty, disc, photo_filename, desc, category, manufacturer, supplier
            (
                pid,
                article,
                name,
                unit,
                price,
                quantity,
                discount,
                photo,
                description,
                category,
                manufacturer,
                supplier,
            ) = row

            try:
                price = float(price)
            except:
                price = 0.0
            try:
                quantity = int(quantity)
            except:
                quantity = 0
            try:
                discount = float(discount)
            except:
                discount = 0.0

            bg = None
            if quantity == 0:
                bg = OUT_OF_STOCK_BG
            if discount > 15:
                bg = DISCOUNT_BG

            item = tk.Frame(
                self.scroll_frame, bd=1, relief="solid", padx=10, pady=10, bg=bg
            )
            item.pack(pady=5, fill="x")

            # click select
            def make_onclick(r=row, frame=item):
                def _on_click(event=None):
                    self.selected_product_row = r
                    # small visual cue (thicker border)
                    for child in self.scroll_frame.winfo_children():
                        child.configure(highlightthickness=0)
                    frame.configure(highlightbackground="black", highlightthickness=2)

                return _on_click

            item.bind("<Button-1>", make_onclick())
            for child in item.winfo_children():
                child.bind("<Button-1>", make_onclick())

            img_path = safe_image_path(photo)
            pil_img = Image.open(img_path).resize((220, 160))
            tk_img = ImageTk.PhotoImage(pil_img)

            img_label = tk.Label(item, image=tk_img, bg=bg)
            img_label.image = tk_img
            img_label.pack(side="left", padx=10)

            info = tk.Frame(item, bg=bg)
            info.pack(side="left", fill="both", expand=True)

            tk.Label(
                info, text=f"{name} (Артикул: {article})", font=self.title_font, bg=bg
            ).pack(anchor="w")
            tk.Label(
                info, text=f"Категория: {category}", font=self.base_font, bg=bg
            ).pack(anchor="w")
            tk.Label(
                info, text=f"Производитель: {manufacturer}", font=self.base_font, bg=bg
            ).pack(anchor="w")
            tk.Label(
                info, text=f"Поставщик: {supplier}", font=self.base_font, bg=bg
            ).pack(anchor="w")

            if description is None:
                description = ""
            tk.Label(
                info,
                text=f"Описание: {description}",
                font=self.base_font,
                bg=bg,
                wraplength=650,
                justify="left",
            ).pack(anchor="w")

            tk.Label(
                info, text=f"Кол-во на складе: {quantity}", font=self.base_font, bg=bg
            ).pack(anchor="w")
            tk.Label(
                info, text=f"Скидка: {discount}%", font=self.base_font, bg=bg
            ).pack(anchor="w")

            price_frame = tk.Frame(info, bg=bg)
            price_frame.pack(anchor="w", pady=3)

            if discount > 0:
                new_price = discounted_price(price, discount)
                tk.Label(
                    price_frame,
                    text=f"{price:.2f}",
                    font=self.old_price_font,
                    fg="red",
                    bg=bg,
                ).pack(side="left")
                tk.Label(
                    price_frame, text=f"  {new_price:.2f}", font=self.base_font, bg=bg
                ).pack(side="left")
            else:
                tk.Label(
                    price_frame, text=f"{price:.2f}", font=self.base_font, bg=bg
                ).pack(side="left")

    def add_product(self):
        ProductForm(self.window, self, mode="add")

    def edit_product(self):
        if not self.selected_product_row:
            messagebox.showwarning(
                "Внимание", "Сначала выберите товар (клик по карточке)."
            )
            return
        ProductForm(
            self.window, self, mode="edit", product_row=self.selected_product_row
        )

    def delete_product(self):
        if not self.selected_product_row:
            messagebox.showwarning(
                "Внимание", "Сначала выберите товар (клик по карточке)."
            )
            return

        pid = self.selected_product_row[0]
        article = self.selected_product_row[1]

        # Check order_items restriction
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM order_items WHERE product_article=?", (article,)
        )
        count = cur.fetchone()[0]
        if count > 0:
            conn.close()
            messagebox.showerror(
                "Ошибка", "Нельзя удалить товар, который присутствует в заказах."
            )
            return

        if not messagebox.askyesno("Подтверждение", "Удалить выбранный товар?"):
            conn.close()
            return

        cur.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        self.refresh()


def open_products_window(user_name, role):
    ProductsUI(user_name, role)


def login():
    login_value = login_entry.get().strip()
    password_value = password_entry.get().strip()

    result = authenticate(login_value, password_value)
    if result:
        user_name, role = result
        open_products_window(user_name, role)
    else:
        messagebox.showerror("Ошибка", "Неверный логин или пароль")


def guest_login():
    open_products_window("Гость", "guest")


root = tk.Tk()
root.title("Вход")
root.geometry("400x300")

title = tk.Label(root, text="Система магазина обуви", font=("Times New Roman", 16))
title.pack(pady=20)

login_label = tk.Label(root, text="Логин", font=("Times New Roman", 12))
login_label.pack()

login_entry = tk.Entry(root)
login_entry.pack()

password_label = tk.Label(root, text="Пароль", font=("Times New Roman", 12))
password_label.pack()

password_entry = tk.Entry(root, show="*")
password_entry.pack()

login_button = tk.Button(root, text="Войти", command=login)
login_button.pack(pady=10)

guest_button = tk.Button(root, text="Войти как гость", command=guest_login)
guest_button.pack()

root.mainloop()
