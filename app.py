import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
from html import escape
import resend


# =========================================================
# CONFIGURATION
# =========================================================

DATABASE = "store.db"

st.set_page_config(
    page_title="My Online Store",
    page_icon="Store",
    layout="wide"
)


# =========================================================
# RESEND EMAIL CONFIGURATION
# =========================================================

def get_resend_api_key():
    """
    Gets the Resend API key from Streamlit Secrets.

    Expected secrets:
        RESEND_API_KEY = "re_xxxxxxxxx"
        EMAIL_FROM = "My Online Store <onboarding@resend.dev>"
    """

    try:
        return st.secrets["RESEND_API_KEY"]
    except Exception:
        return None


def get_email_from():
    """
    Gets the email address/name used as the sender.
    """

    try:
        return st.secrets["EMAIL_FROM"]
    except Exception:
        return "My Online Store <onboarding@resend.dev>"


def send_order_confirmation_email(
    customer_email,
    customer_name,
    order_id,
    order_total,
    payment_method,
    order_date,
    order_items
):
    """
    Sends an order confirmation email through Resend.

    Returns:
        True, message
    or
        False, error message
    """

    api_key = get_resend_api_key()

    if not api_key:
        return (
            False,
            "Resend API key is not configured in Streamlit Secrets."
        )

    if not customer_email:
        return (
            False,
            "Customer does not have an email address."
        )

    try:

        resend.api_key = api_key

        # Build the product rows for the email
        item_rows = ""

        for item in order_items:

            subtotal = (
                item["price"] * item["quantity"]
            )

            item_rows += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">
                        {escape(str(item["product_name"]))}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: center;">
                        {item["quantity"]}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">
                        ${item["price"]:.2f}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">
                        ${subtotal:.2f}
                    </td>
                </tr>
            """

        safe_name = escape(str(customer_name))
        safe_payment = escape(str(payment_method))
        safe_date = escape(str(order_date))

        email_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Order Confirmation</title>
        </head>

        <body style="
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 20px;
        ">

            <div style="
                max-width: 700px;
                margin: auto;
                background-color: white;
                padding: 30px;
                border-radius: 10px;
            ">

                <h1 style="text-align: center;">
                    Order Confirmation
                </h1>

                <p>
                    Hello <strong>{safe_name}</strong>,
                </p>

                <p>
                    Thank you for your purchase.
                    Your order has been successfully completed.
                </p>

                <hr>

                <h2>Order Information</h2>

                <p>
                    <strong>Order Number:</strong> #{order_id}
                </p>

                <p>
                    <strong>Order Date:</strong> {safe_date}
                </p>

                <p>
                    <strong>Payment Method:</strong> {safe_payment}
                </p>

                <p>
                    <strong>Status:</strong> Completed
                </p>

                <h2>Products</h2>

                <table style="
                    width: 100%;
                    border-collapse: collapse;
                ">

                    <thead>
                        <tr style="background-color: #f0f0f0;">
                            <th style="padding: 10px; text-align: left;">
                                Product
                            </th>

                            <th style="padding: 10px; text-align: center;">
                                Quantity
                            </th>

                            <th style="padding: 10px; text-align: right;">
                                Price
                            </th>

                            <th style="padding: 10px; text-align: right;">
                                Subtotal
                            </th>
                        </tr>
                    </thead>

                    <tbody>
                        {item_rows}
                    </tbody>

                </table>

                <hr>

                <h2 style="text-align: right;">
                    Total: ${order_total:.2f}
                </h2>

                <p>
                    Thank you for shopping with us.
                </p>

                <p>
                    My Online Store
                </p>

            </div>

        </body>
        </html>
        """

        params = {
            "from": get_email_from(),
            "to": [customer_email],
            "subject": f"Order Confirmation #{order_id}",
            "html": email_html
        }

        result = resend.Emails.send(params)

        return True, result

    except Exception as error:

        return False, str(error)


# =========================================================
# DATABASE
# =========================================================

def get_connection():

    conn = sqlite3.connect(
        DATABASE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


def add_missing_column(
    conn,
    table_name,
    column_name,
    column_type
):

    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    existing_columns = [
        column["name"]
        for column in columns
    ]

    if column_name not in existing_columns:

        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_type}
            """
        )


def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    # =====================================================
    # USERS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer'
        )
    """)

    # Add email column to existing databases
    add_missing_column(
        conn,
        "users",
        "email",
        "TEXT"
    )

    # =====================================================
    # PRODUCTS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            inventory INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Add image columns to existing databases
    add_missing_column(
        conn,
        "products",
        "image_data",
        "BLOB"
    )

    add_missing_column(
        conn,
        "products",
        "image_type",
        "TEXT"
    )

    # =====================================================
    # ORDERS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL,
            order_date TEXT NOT NULL
        )
    """)

    # =====================================================
    # ORDER ITEMS
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id)
                REFERENCES orders(id)
        )
    """)

    # =====================================================
    # DEFAULT ADMIN
    # =====================================================

    admin_password = hash_password(
        "admin123"
    )

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (
            username,
            password,
            role,
            email
        )
        VALUES (?, ?, ?, ?)
    """, (
        "admin",
        admin_password,
        "admin",
        None
    ))

    # =====================================================
    # SAMPLE PRODUCTS
    # =====================================================

    cursor.execute(
        "SELECT COUNT(*) FROM products"
    )

    product_count = cursor.fetchone()[0]

    if product_count == 0:

        sample_products = [

            (
                "Wireless Headphones",
                "Comfortable wireless headphones with Bluetooth.",
                59.99,
                20
            ),

            (
                "Mechanical Keyboard",
                "A mechanical keyboard suitable for gaming and schoolwork.",
                79.99,
                15
            ),

            (
                "Gaming Mouse",
                "High-precision mouse with adjustable DPI.",
                39.99,
                25
            ),

            (
                "USB-C Cable",
                "Durable USB-C charging and data cable.",
                12.99,
                50
            )

        ]

        cursor.executemany("""
            INSERT INTO products
            (
                name,
                description,
                price,
                inventory
            )
            VALUES (?, ?, ?, ?)
        """, sample_products)

    conn.commit()
    conn.close()


# =========================================================
# USER FUNCTIONS
# =========================================================

def get_user(username):

    conn = get_connection()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE username = ?
    """, (
        username,
    )).fetchone()

    conn.close()

    return user


def create_user(
    username,
    password,
    email
):

    conn = get_connection()

    try:

        conn.execute("""
            INSERT INTO users
            (
                username,
                password,
                role,
                email
            )
            VALUES (?, ?, ?, ?)
        """, (
            username,
            hash_password(password),
            "customer",
            email
        ))

        conn.commit()

        success = True

    except sqlite3.IntegrityError:

        success = False

    conn.close()

    return success


def authenticate_user(
    username,
    password
):

    user = get_user(username)

    if user is None:

        return None

    if user["password"] == hash_password(password):

        return user

    return None


# =========================================================
# PRODUCT FUNCTIONS
# =========================================================

def get_all_products():

    conn = get_connection()

    products = conn.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return products


def get_product(product_id):

    conn = get_connection()

    product = conn.execute("""
        SELECT *
        FROM products
        WHERE id = ?
    """, (
        product_id,
    )).fetchone()

    conn.close()

    return product


def add_product(
    name,
    description,
    price,
    inventory,
    image_data=None,
    image_type=None
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO products
        (
            name,
            description,
            price,
            inventory,
            image_data,
            image_type
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        name,
        description,
        price,
        inventory,
        image_data,
        image_type
    ))

    conn.commit()
    conn.close()


def update_product(
    product_id,
    name,
    description,
    price,
    inventory,
    image_data=None,
    image_type=None,
    update_image=False
):

    conn = get_connection()

    if update_image:

        conn.execute("""
            UPDATE products
            SET
                name = ?,
                description = ?,
                price = ?,
                inventory = ?,
                image_data = ?,
                image_type = ?
            WHERE id = ?
        """, (
            name,
            description,
            price,
            inventory,
            image_data,
            image_type,
            product_id
        ))

    else:

        conn.execute("""
            UPDATE products
            SET
                name = ?,
                description = ?,
                price = ?,
                inventory = ?
            WHERE id = ?
        """, (
            name,
            description,
            price,
            inventory,
            product_id
        ))

    conn.commit()
    conn.close()


def delete_product(product_id):

    conn = get_connection()

    conn.execute("""
        DELETE FROM products
        WHERE id = ?
    """, (
        product_id,
    ))

    conn.commit()
    conn.close()


# =========================================================
# ORDER FUNCTIONS
# =========================================================

def create_order(
    username,
    cart,
    payment_method
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("BEGIN")

        total = 0

        # ---------------------------------------------
        # Check inventory
        # ---------------------------------------------

        for product_id, quantity in cart.items():

            product = cursor.execute("""
                SELECT *
                FROM products
                WHERE id = ?
            """, (
                product_id,
            )).fetchone()

            if product is None:

                raise Exception(
                    "A product in your cart no longer exists."
                )

            if product["inventory"] < quantity:

                raise Exception(
                    f"Not enough inventory for "
                    f"{product['name']}."
                )

            total += (
                product["price"] * quantity
            )

        # ---------------------------------------------
        # Create order
        # ---------------------------------------------

        order_date = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute("""
            INSERT INTO orders
            (
                username,
                total,
                payment_method,
                status,
                order_date
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            username,
            total,
            payment_method,
            "Completed",
            order_date
        ))

        order_id = cursor.lastrowid

        # ---------------------------------------------
        # Add order items
        # ---------------------------------------------

        for product_id, quantity in cart.items():

            product = cursor.execute("""
                SELECT *
                FROM products
                WHERE id = ?
            """, (
                product_id,
            )).fetchone()

            cursor.execute("""
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    product_name,
                    quantity,
                    price
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                product_id,
                product["name"],
                quantity,
                product["price"]
            ))

            # -----------------------------------------
            # Decrease inventory
            # -----------------------------------------

            cursor.execute("""
                UPDATE products
                SET inventory = inventory - ?
                WHERE id = ?
            """, (
                quantity,
                product_id
            ))

        conn.commit()

        return True, order_id, total

    except Exception as error:

        conn.rollback()

        return False, str(error), 0

    finally:

        conn.close()


def get_customer_orders(username):

    conn = get_connection()

    orders = conn.execute("""
        SELECT *
        FROM orders
        WHERE username = ?
        ORDER BY id DESC
    """, (
        username,
    )).fetchall()

    conn.close()

    return orders


def get_order_items(order_id):

    conn = get_connection()

    items = conn.execute("""
        SELECT *
        FROM order_items
        WHERE order_id = ?
    """, (
        order_id,
    )).fetchall()

    conn.close()

    return items


def get_all_orders():

    conn = get_connection()

    orders = conn.execute("""
        SELECT *
        FROM orders
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return orders


def get_all_users():

    conn = get_connection()

    users = conn.execute("""
        SELECT
            id,
            username,
            email,
            role
        FROM users
        ORDER BY id
    """).fetchall()

    conn.close()

    return users


# =========================================================
# SESSION STATE
# =========================================================

def initialize_session():

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "username" not in st.session_state:
        st.session_state.username = ""

    if "role" not in st.session_state:
        st.session_state.role = ""

    if "cart" not in st.session_state:
        st.session_state.cart = {}

    if "page" not in st.session_state:
        st.session_state.page = "Store"


# =========================================================
# LOGIN PAGE
# =========================================================

def login_page():

    st.title("My Online Store")
    st.subheader("Login")

    login_tab, register_tab = st.tabs([
        "Login",
        "Create Customer Account"
    ])

    # =====================================================
    # LOGIN
    # =====================================================

    with login_tab:

        with st.form("login_form"):

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Login",
                use_container_width=True
            )

            if submitted:

                if not username or not password:

                    st.error(
                        "Please enter both username and password."
                    )

                else:

                    user = authenticate_user(
                        username,
                        password
                    )

                    if user:

                        st.session_state.logged_in = True
                        st.session_state.username = \
                            user["username"]

                        st.session_state.role = \
                            user["role"]

                        if user["role"] == "admin":

                            st.session_state.page = \
                                "Admin Dashboard"

                        else:

                            st.session_state.page = \
                                "Store"

                        st.success(
                            "Login successful."
                        )

                        st.rerun()

                    else:

                        st.error(
                            "Invalid username or password."
                        )

        st.info(
            "Demo admin account: "
            "username = admin, password = admin123"
        )

    # =====================================================
    # REGISTER
    # =====================================================

    with register_tab:

        with st.form("register_form"):

            new_username = st.text_input(
                "Choose a username"
            )

            new_email = st.text_input(
                "Email Address",
                placeholder="customer@example.com"
            )

            new_password = st.text_input(
                "Choose a password",
                type="password"
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password"
            )

            register = st.form_submit_button(
                "Create Account",
                use_container_width=True
            )

            if register:

                if (
                    not new_username
                    or not new_email
                    or not new_password
                ):

                    st.error(
                        "Please complete all fields."
                    )

                elif len(new_username) < 3:

                    st.error(
                        "Username must contain "
                        "at least 3 characters."
                    )

                elif "@" not in new_email:

                    st.error(
                        "Please enter a valid email address."
                    )

                elif len(new_password) < 6:

                    st.error(
                        "Password must contain "
                        "at least 6 characters."
                    )

                elif new_password != confirm_password:

                    st.error(
                        "Passwords do not match."
                    )

                else:

                    success = create_user(
                        new_username,
                        new_password,
                        new_email
                    )

                    if success:

                        st.success(
                            "Account created. "
                            "You can now log in."
                        )

                    else:

                        st.error(
                            "That username is already taken."
                        )


# =========================================================
# CUSTOMER STORE
# =========================================================

def customer_store():

    st.title("Online Store")

    st.write(
        f"Welcome, **{st.session_state.username}**."
    )

    products = get_all_products()

    if not products:

        st.warning(
            "There are currently no products."
        )

        return

    st.subheader("Products")

    search = st.text_input(
        "Search products",
        placeholder="Search by product name..."
    )

    filtered_products = []

    for product in products:

        if search.lower() in product["name"].lower():

            filtered_products.append(product)

    if not filtered_products:

        st.info(
            "No products match your search."
        )

        return

    columns = st.columns(3)

    for index, product in enumerate(
        filtered_products
    ):

        with columns[index % 3]:

            st.markdown("---")

            # -----------------------------------------
            # Product image
            # -----------------------------------------

            if product["image_data"]:

                st.image(
                    product["image_data"],
                    use_container_width=True
                )

            else:

                st.info(
                    "No product image"
                )

            # -----------------------------------------
            # Product details
            # -----------------------------------------

            st.subheader(
                product["name"]
            )

            if product["description"]:

                st.write(
                    product["description"]
                )

            st.write(
                f"**Price:** "
                f"${product['price']:.2f}"
            )

            # -----------------------------------------
            # Inventory
            # -----------------------------------------

            if product["inventory"] > 0:

                st.write(
                    f"**In stock:** "
                    f"{product['inventory']}"
                )

                quantity = st.number_input(
                    "Quantity",
                    min_value=1,
                    max_value=product["inventory"],
                    value=1,
                    step=1,
                    key=f"quantity_{product['id']}"
                )

                if st.button(
                    "Add to Cart",
                    key=f"add_{product['id']}",
                    use_container_width=True
                ):

                    current_quantity = (
                        st.session_state.cart.get(
                            product["id"],
                            0
                        )
                    )

                    new_quantity = (
                        current_quantity
                        + quantity
                    )

                    if new_quantity > \
                            product["inventory"]:

                        st.error(
                            "You cannot add more than "
                            "the available inventory."
                        )

                    else:

                        st.session_state.cart[
                            product["id"]
                        ] = new_quantity

                        st.success(
                            f"Added {quantity} "
                            f"item(s) to cart."
                        )

            else:

                st.error(
                    "Out of stock"
                )


# =========================================================
# SHOPPING CART
# =========================================================

def shopping_cart():

    st.title("Shopping Cart")

    cart = st.session_state.cart

    if not cart:

        st.info(
            "Your cart is empty."
        )

        return

    total = 0

    for product_id, quantity in list(
        cart.items()
    ):

        product = get_product(
            product_id
        )

        if product is None:

            del st.session_state.cart[
                product_id
            ]

            continue

        item_total = (
            product["price"]
            * quantity
        )

        total += item_total

        col1, col2, col3, col4 = st.columns(
            [3, 1, 1, 1]
        )

        with col1:

            st.write(
                f"**{product['name']}**"
            )

        with col2:

            st.write(
                f"${product['price']:.2f}"
            )

        with col3:

            st.write(
                f"Quantity: {quantity}"
            )

        with col4:

            if st.button(
                "Remove",
                key=f"remove_{product_id}"
            ):

                del st.session_state.cart[
                    product_id
                ]

                st.rerun()

    st.markdown("---")

    st.subheader(
        f"Total: ${total:.2f}"
    )

    if st.button(
        "Clear Cart",
        use_container_width=True
    ):

        st.session_state.cart = {}

        st.rerun()

    st.markdown("---")

    # =====================================================
    # CHECKOUT
    # =====================================================

    st.subheader("Checkout")

    payment_method = st.selectbox(
        "Payment Method",
        [
            "Credit/Debit Card",
            "PayPal",
            "Cash on Delivery"
        ]
    )

    # =====================================================
    # CARD
    # =====================================================

    if payment_method == "Credit/Debit Card":

        card_number = st.text_input(
            "Card Number",
            type="password",
            placeholder="Enter a demo card number"
        )

        col1, col2 = st.columns(2)

        with col1:

            expiry = st.text_input(
                "Expiry Date",
                placeholder="MM/YY"
            )

        with col2:

            cvv = st.text_input(
                "CVV",
                type="password",
                placeholder="123"
            )

    # =====================================================
    # PAYPAL
    # =====================================================

    elif payment_method == "PayPal":

        paypal_email = st.text_input(
            "PayPal Email"
        )

    # =====================================================
    # CASH
    # =====================================================

    else:

        st.info(
            "You selected Cash on Delivery."
        )

    st.warning(
        "This is a school-project payment simulation. "
        "Do not enter a real credit card number."
    )

    # =====================================================
    # COMPLETE ORDER
    # =====================================================

    if st.button(
        "Complete Order",
        type="primary",
        use_container_width=True
    ):

        payment_valid = True

        # ---------------------------------------------
        # Validate card
        # ---------------------------------------------

        if payment_method == "Credit/Debit Card":

            if (
                not card_number
                or not expiry
                or not cvv
            ):

                payment_valid = False

                st.error(
                    "Please complete the demo "
                    "payment fields."
                )

        # ---------------------------------------------
        # Validate PayPal
        # ---------------------------------------------

        elif payment_method == "PayPal":

            if not paypal_email:

                payment_valid = False

                st.error(
                    "Please enter a PayPal email."
                )

        # ---------------------------------------------
        # Create order
        # ---------------------------------------------

        if payment_valid:

            success, result, order_total = create_order(
                st.session_state.username,
                st.session_state.cart,
                payment_method
            )

            if success:

                order_id = result

                # -------------------------------------
                # Get customer information
                # -------------------------------------

                customer = get_user(
                    st.session_state.username
                )

                customer_email = None

                if customer:

                    customer_email = customer["email"]

                # -------------------------------------
                # Get order items
                # -------------------------------------

                order_items = get_order_items(
                    order_id
                )

                order_date = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                # -------------------------------------
                # Clear shopping cart
                # -------------------------------------

                st.session_state.cart = {}

                # -------------------------------------
                # Display success
                # -------------------------------------

                st.success(
                    "Order completed successfully."
                )

                st.info(
                    f"Your order number is #{order_id}"
                )

                st.write(
                    f"**Order Total:** "
                    f"${order_total:.2f}"
                )

                # -------------------------------------
                # Send email
                # -------------------------------------

                if customer_email:

                    email_success, email_result = (
                        send_order_confirmation_email(
                            customer_email,
                            st.session_state.username,
                            order_id,
                            order_total,
                            payment_method,
                            order_date,
                            order_items
                        )
                    )

                    if email_success:

                        st.success(
                            f"Order confirmation sent to "
                            f"{customer_email}."
                        )

                    else:

                        st.warning(
                            "The order was completed, "
                            "but the confirmation email "
                            "could not be sent."
                        )

                        st.caption(
                            f"Email service message: "
                            f"{email_result}"
                        )

                else:

                    st.warning(
                        "The order was completed, "
                        "but this account does not "
                        "have an email address."
                    )

            else:

                st.error(
                    f"Order could not be completed: "
                    f"{result}"
                )


# =========================================================
# CUSTOMER ORDER HISTORY
# =========================================================

def customer_order_history():

    st.title("My Order History")

    orders = get_customer_orders(
        st.session_state.username
    )

    if not orders:

        st.info(
            "You have not placed any orders yet."
        )

        return

    for order in orders:

        with st.expander(
            f"Order #{order['id']} - "
            f"${order['total']:.2f} - "
            f"{order['order_date']}"
        ):

            st.write(
                f"**Status:** "
                f"{order['status']}"
            )

            st.write(
                f"**Payment:** "
                f"{order['payment_method']}"
            )

            items = get_order_items(
                order["id"]
            )

            st.write("### Items")

            for item in items:

                subtotal = (
                    item["price"]
                    * item["quantity"]
                )

                st.write(
                    f"{item['product_name']} "
                    f"x {item['quantity']} = "
                    f"${subtotal:.2f}"
                )

            st.write(
                f"**Total: "
                f"${order['total']:.2f}**"
            )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

def admin_dashboard():

    st.title("Admin Dashboard")

    st.write(
        f"Logged in as "
        f"**{st.session_state.username}**"
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "Products",
        "Add Product",
        "Orders",
        "Users"
    ])

    # =====================================================
    # PRODUCTS
    # =====================================================

    with tab1:

        st.subheader(
            "Manage Products"
        )

        products = get_all_products()

        if not products:

            st.info(
                "There are no products yet."
            )

        for product in products:

            with st.expander(
                f"{product['name']} - "
                f"${product['price']:.2f} - "
                f"Inventory: "
                f"{product['inventory']}"
            ):

                # -----------------------------------------
                # Current image
                # -----------------------------------------

                if product["image_data"]:

                    st.write(
                        "Current Product Image:"
                    )

                    st.image(
                        product["image_data"],
                        width=250
                    )

                else:

                    st.info(
                        "This product does not "
                        "have an image."
                    )

                col1, col2 = st.columns(2)

                # -----------------------------------------
                # Name and description
                # -----------------------------------------

                with col1:

                    name = st.text_input(
                        "Product Name",
                        value=product["name"],
                        key=f"edit_name_{product['id']}"
                    )

                    description = st.text_area(
                        "Description",
                        value=product["description"] or "",
                        key=f"edit_desc_{product['id']}"
                    )

                # -----------------------------------------
                # Price and inventory
                # -----------------------------------------

                with col2:

                    price = st.number_input(
                        "Price",
                        min_value=0.0,
                        value=float(
                            product["price"]
                        ),
                        step=0.01,
                        key=f"edit_price_{product['id']}"
                    )

                    inventory = st.number_input(
                        "Inventory",
                        min_value=0,
                        value=int(
                            product["inventory"]
                        ),
                        step=1,
                        key=f"edit_inventory_{product['id']}"
                    )

                # -----------------------------------------
                # Upload new image
                # -----------------------------------------

                uploaded_image = st.file_uploader(
                    "Change Product Image",
                    type=[
                        "png",
                        "jpg",
                        "jpeg",
                        "webp"
                    ],
                    key=f"edit_image_{product['id']}"
                )

                if uploaded_image:

                    st.write(
                        "New Image Preview:"
                    )

                    st.image(
                        uploaded_image,
                        width=250
                    )

                # -----------------------------------------
                # Remove image
                # -----------------------------------------

                remove_image = st.checkbox(
                    "Remove current image",
                    key=f"remove_image_{product['id']}"
                )

                col_save, col_delete = st.columns(2)

                # -----------------------------------------
                # Save
                # -----------------------------------------

                with col_save:

                    if st.button(
                        "Save Changes",
                        key=f"save_{product['id']}",
                        use_container_width=True
                    ):

                        if not name.strip():

                            st.error(
                                "Product name cannot be empty."
                            )

                        elif remove_image:

                            update_product(
                                product["id"],
                                name,
                                description,
                                price,
                                inventory,
                                image_data=None,
                                image_type=None,
                                update_image=True
                            )

                            st.success(
                                "Product updated "
                                "and image removed."
                            )

                            st.rerun()

                        elif uploaded_image:

                            image_data = (
                                uploaded_image.getvalue()
                            )

                            image_type = (
                                uploaded_image.type
                            )

                            update_product(
                                product["id"],
                                name,
                                description,
                                price,
                                inventory,
                                image_data=image_data,
                                image_type=image_type,
                                update_image=True
                            )

                            st.success(
                                "Product and image updated."
                            )

                            st.rerun()

                        else:

                            update_product(
                                product["id"],
                                name,
                                description,
                                price,
                                inventory
                            )

                            st.success(
                                "Product updated."
                            )

                            st.rerun()

                # -----------------------------------------
                # Delete
                # -----------------------------------------

                with col_delete:

                    if st.button(
                        "Delete Product",
                        key=f"delete_{product['id']}",
                        use_container_width=True
                    ):

                        delete_product(
                            product["id"]
                        )

                        st.success(
                            "Product deleted."
                        )

                        st.rerun()

    # =====================================================
    # ADD PRODUCT
    # =====================================================

    with tab2:

        st.subheader(
            "Add New Product"
        )

        with st.form(
            "add_product_form"
        ):

            name = st.text_input(
                "Product Name"
            )

            description = st.text_area(
                "Description"
            )

            price = st.number_input(
                "Price",
                min_value=0.0,
                value=10.0,
                step=0.01
            )

            inventory = st.number_input(
                "Inventory",
                min_value=0,
                value=10,
                step=1
            )

            uploaded_image = st.file_uploader(
                "Product Image",
                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp"
                ],
                help=(
                    "Upload a PNG, JPG, JPEG, "
                    "or WEBP image."
                )
            )

            if uploaded_image:

                st.write(
                    "Image Preview:"
                )

                st.image(
                    uploaded_image,
                    width=300
                )

            submitted = st.form_submit_button(
                "Add Product",
                use_container_width=True
            )

            if submitted:

                if not name.strip():

                    st.error(
                        "Product name is required."
                    )

                elif price < 0:

                    st.error(
                        "Price cannot be negative."
                    )

                else:

                    image_data = None
                    image_type = None

                    if uploaded_image:

                        image_data = (
                            uploaded_image.getvalue()
                        )

                        image_type = (
                            uploaded_image.type
                        )

                    add_product(
                        name,
                        description,
                        price,
                        inventory,
                        image_data,
                        image_type
                    )

                    st.success(
                        "Product added successfully."
                    )

                    st.rerun()

    # =====================================================
    # ORDERS
    # =====================================================

    with tab3:

        st.subheader(
            "All Orders"
        )

        orders = get_all_orders()

        if not orders:

            st.info(
                "No orders have been placed yet."
            )

        else:

            for order in orders:

                with st.expander(
                    f"Order #{order['id']} | "
                    f"Customer: "
                    f"{order['username']} | "
                    f"${order['total']:.2f}"
                ):

                    customer = get_user(
                        order["username"]
                    )

                    if customer and customer["email"]:

                        st.write(
                            f"**Customer Email:** "
                            f"{customer['email']}"
                        )

                    st.write(
                        f"**Date:** "
                        f"{order['order_date']}"
                    )

                    st.write(
                        f"**Payment:** "
                        f"{order['payment_method']}"
                    )

                    st.write(
                        f"**Status:** "
                        f"{order['status']}"
                    )

                    items = get_order_items(
                        order["id"]
                    )

                    st.write(
                        "### Products"
                    )

                    for item in items:

                        st.write(
                            f"- "
                            f"{item['product_name']} "
                            f"x {item['quantity']} "
                            f"(${item['price']:.2f} each)"
                        )

    # =====================================================
    # USERS
    # =====================================================

    with tab4:

        st.subheader(
            "Registered Users"
        )

        users = get_all_users()

        for user in users:

            email_text = (
                user["email"]
                if user["email"]
                else "No email"
            )

            st.write(
                f"**{user['username']}** "
                f"- Email: {email_text} "
                f"- Role: {user['role']}"
            )


# =========================================================
# SIDEBAR
# =========================================================

def show_sidebar():

    with st.sidebar:

        st.title(
            "Store Menu"
        )

        st.write(
            f"Logged in as: "
            f"**{st.session_state.username}**"
        )

        st.write(
            f"Role: "
            f"**{st.session_state.role.title()}**"
        )

        st.markdown("---")

        # =================================================
        # ADMIN
        # =================================================

        if st.session_state.role == "admin":

            if st.button(
                "Admin Dashboard",
                use_container_width=True
            ):

                st.session_state.page = \
                    "Admin Dashboard"

                st.rerun()

            if st.button(
                "View Store",
                use_container_width=True
            ):

                st.session_state.page = \
                    "Store"

                st.rerun()

        # =================================================
        # CUSTOMER
        # =================================================

        else:

            if st.button(
                "Store",
                use_container_width=True
            ):

                st.session_state.page = \
                    "Store"

                st.rerun()

            if st.button(
                "Shopping Cart",
                use_container_width=True
            ):

                st.session_state.page = \
                    "Cart"

                st.rerun()

            if st.button(
                "Order History",
                use_container_width=True
            ):

                st.session_state.page = \
                    "History"

                st.rerun()

        st.markdown("---")

        # =================================================
        # CART COUNT
        # =================================================

        cart_count = sum(
            st.session_state.cart.values()
        )

        if st.session_state.role == "customer":

            st.write(
                f"Cart items: **{cart_count}**"
            )

        # =================================================
        # LOGOUT
        # =================================================

        if st.button(
            "Logout",
            use_container_width=True
        ):

            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.session_state.cart = {}
            st.session_state.page = "Store"

            st.rerun()


# =========================================================
# START APPLICATION
# =========================================================

initialize_database()
initialize_session()


if not st.session_state.logged_in:

    login_page()

else:

    show_sidebar()

    if st.session_state.role == "admin":

        if st.session_state.page == \
                "Admin Dashboard":

            admin_dashboard()

        else:

            customer_store()

    else:

        if st.session_state.page == "Store":

            customer_store()

        elif st.session_state.page == "Cart":

            shopping_cart()

        elif st.session_state.page == "History":

            customer_order_history()

        else:

            customer_store()
