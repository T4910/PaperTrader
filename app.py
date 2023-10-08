import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
# if not os.environ.get("API_KEY"):
#     raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


##################################

# for my feature of comparable scope, I made it so that
# when a person registers, they are automatically logged in

##################################


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    symbols = []
    symbol_share_num = []

    symbols_data = db.execute("SELECT DISTINCT symbol FROM users_shares WHERE user_id = ?", session["user_id"])

    for i in range(len(symbols_data)):
        symbols.append(symbols_data[i]['symbol'])
        placeholder = {}
        symnum = db.execute(
            "SELECT symbol, SUM(numshares) AS share_num FROM users_shares GROUP BY symbol, user_id HAVING user_id = ?", session["user_id"])[i]

        if symnum['share_num'] < 1:
            symbols.pop()
            continue

        lookup_val = lookup(symnum['symbol'])

        placeholder = {
            "stockname": lookup_val['name'],
            "price": lookup_val['price'],
            "symbol": symnum['symbol'],
            "numofshares": symnum['share_num'],
            "totalcost": round((lookup_val['price'] * symnum['share_num']), 2)
        }

        symbol_share_num.append(placeholder)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    profits = cash

    for i in range(len(symbol_share_num)):
        profits += symbol_share_num[i]["totalcost"]

    return render_template("portfolio.html", portdatas=symbol_share_num, cash=cash, profits=profits)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # POST request
    if request.method == "POST":

        # to confirm share has been bought
        success = 0
        # to control that the popup is shown
        show = 0
####
        # To know which user is on
        user_id = session["user_id"]
        user_symbol = request.form.get("symbol")
        user_shareno = request.form.get("shares")

        # # POPUP CODE BLOCK
        if request.form.get("reveal") == '1':

            buying_info = db.execute("SELECT symbol, share_num FROM temp_info WHERE user_id = ?", user_id)
            user_symbol = buying_info[0]["symbol"]
            user_shareno = buying_info[0]["share_num"]
            show = 1

        elif not request.form.get("reveal"):
            print("no show")

        else:
            return apology("Sorry, something went wrong with the purchase", 400)

        # NO PRESS CODE BLOCK
        if request.form.get("no_purchase") == '1':

            buying_info = db.execute("SELECT symbol, share_num FROM temp_info WHERE user_id = ?", user_id)
            user_symbol = buying_info[0]["symbol"]
            user_shareno = buying_info[0]["share_num"]

            # delete any temporary data in database
            db.execute("DELETE FROM temp_info WHERE user_id = ?", user_id)

            return redirect("/buy")

        elif not request.form.get("no_purchase"):
            print("not yet")

        else:
            return apology("Sorry, something went wrong with the purchase", 500)

        # YES PRESS CODE BLOCK
        # only when confirmation is success
        if request.form.get("purchase") == '1':

            buying_info = db.execute("SELECT symbol, share_num FROM temp_info WHERE user_id = ?", user_id)

            # when user wants to reload the page when on bought state
            if len(buying_info) == 0:
                return redirect("/buy")

            # delete the temporary database placement
            db.execute("DELETE FROM temp_info WHERE user_id = ?", user_id)

            user_symbol = buying_info[0]["symbol"]
            user_shareno = buying_info[0]["share_num"]
            success = 1
            show = 0

            # add the share transaction info to the users_shares table

            leftcash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"] - ((lookup(user_symbol)['price'])*user_shareno) # Remaining cash at that point in time

            # prevent buying stock that user can't afford
            if leftcash < 0:
                return apology("You do not have enough money")

            db.execute("UPDATE users SET cash = ? WHERE id = ?", leftcash, user_id)
            time_bought = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # near perfect time in which users cash was deducted
            db.execute("INSERT INTO users_shares (user_id, symbol, numshares, price, time, newcash, transaction_type) VALUES (?, ?, ?, ?, ?, ?, 'bought')",
                        user_id, user_symbol, user_shareno, lookup(user_symbol)['price'], time_bought, round(leftcash, 2))

            return redirect("/")

        elif not(request.form.get("purchase")):
            print("no form")

        else:
            if not user_symbol:
                return apology("Sorry, something went wrong with the purchase", 400)
            elif not user_shareno:
                return apology("Sorry, something went wrong with the purchase", 400)

            return apology("Sorry, something went wrong with the purchase", 400)


        # Validations
        if not user_symbol:
            return apology("must provide a share symbol", 400)
        elif not user_shareno:
            return apology("must provide number of shares", 400)

        if str(lookup(user_symbol)) == "None":  # checks if symbol is valid
            return apology("must provide a valid symbol", 400)

        # declares and modifies needed variables
        try:
            if int(user_shareno) > 0:
                num_shares = int(user_shareno)
                share_data = lookup(user_symbol)
                user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
            else:
                return apology("must provide a valid number of shares", 400)
        except:
            return apology("must provide a valid number of shares", 400)

        buying_related_data = {
            "popup_state": show,
            "bought_state": success,
            "stockname": share_data["name"],
            "symbol": share_data["symbol"],
            "price": share_data["price"],
            "numofshares": num_shares,
            "totalcost": (share_data["price"] * num_shares),
            "leftcash": round(user_cash[0]["cash"] - (share_data["price"] * num_shares), 2),
            "totalcash": ((share_data["price"] * num_shares) + (user_cash[0]["cash"] - (share_data["price"] * num_shares)))
        }

        if not request.form.get("purchase"):
            db.execute("INSERT INTO temp_info (user_id, symbol, share_num) VALUES (?, ?, ?)",
                    user_id, buying_related_data["symbol"], buying_related_data["numofshares"])

        return render_template("buying.html", buydatas=buying_related_data, cash=user_cash[0]["cash"])


        # The reason you see 1 == 1 in any line of code below is because
        # I had initially designed this thing to have a popup hence all
        # the commenting on top
        # If you comment everything from this point right before the
        # 'return render_template("buying.html", buydatas=buying_related_data, cash=user_cash[0]["cash"])'
        # uncomment the:
        # 'if not request.form.get("purchase"):', tab where necessary
        # and
        # uncomment all the lines of code above, then change the variables
        # success and show to 0;
        # You will get the initial popup design I built for this page

        # # POPUP CODE BLOCK
        # if 1 == 1:  # request.form.get("reveal") == '1':

        #     buying_info = db.execute("SELECT symbol, share_num FROM temp_info WHERE user_id = ?", user_id)
        #     user_symbol = buying_info[0]["symbol"]
        #     user_shareno = buying_info[0]["share_num"]
        #     show = 1

        # elif not request.form.get("reveal"):
        #     print("no show")

        # else:
        #     return apology("Sorry, something went wrong with the purchase", 400)

        # # NO PRESS CODE BLOCK
        # if request.form.get("no_purchase") == '1':

        #     buying_info = db.execute("SELECT symbol, share_num FROM temp_info WHERE user_id = ?", user_id)
        #     user_symbol = buying_info[0]["symbol"]
        #     user_shareno = buying_info[0]["share_num"]

        #     # delete any temporary data in database
        #     db.execute("DELETE FROM temp_info WHERE user_id = ?", user_id)

        #     return redirect("/buy")

        # elif not request.form.get("no_purchase"):
        #     print("not yet")

        # else:
        #     return apology("Sorry, something went wrong with the purchase", 500)

        # # YES PRESS CODE BLOCK
        # # only when confirmation is success
        # if 1 == 1:  # request.form.get("purchase") == '1':

        #     buying_info = db.execute("SELECT symbol, share_num FROM temp_info WHERE user_id = ?", user_id)

        #     # when user wants to reload the page when on bought state
        #     if len(buying_info) == 0:
        #         return redirect("/buy")

        #     # delete the temporary database placement
        #     db.execute("DELETE FROM temp_info WHERE user_id = ?", user_id)

        #     user_symbol = buying_info[0]["symbol"]
        #     user_shareno = buying_info[0]["share_num"]
        #     success = 1
        #     show = 0

        #     # add the share transaction info to the users_shares table
        #     # Remaining cash at that point in time
        #     usercashed = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        #     userpriced = ((lookup(user_symbol)['price'])*user_shareno)

        #     leftcash = usercashed - userpriced

        #     # prevent buying stock that user can't afford
        #     if leftcash < 0:
        #         return apology("You do not have enough money")

        #     db.execute("UPDATE users SET cash = ? WHERE id = ?", leftcash, user_id)
        #     time_bought = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # near perfect time in which users cash was deducted
        #     db.execute("INSERT INTO users_shares (user_id, symbol, numshares, price, time, newcash, transaction_type) VALUES (?, ?, ?, ?, ?, ?, 'bought')",
        #                user_id, user_symbol, user_shareno, lookup(user_symbol)['price'], time_bought, round(leftcash, 2))

        #     return redirect("/")

        # elif not(request.form.get("purchase")):
        #     print("no form")

        # else:
        #     if not user_symbol:
        #         return apology("Sorry, something went wrong with the purchase", 400)
        #     elif not user_shareno:
        #         return apology("Sorry, something went wrong with the purchase", 400)

        #     return apology("Sorry, something went wrong with the purchase", 400)


    # GET request
    else:
        db.execute("DELETE FROM temp_info WHERE user_id = ?", session['user_id'])
        return render_template("buy_form.html", cash=db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # get users history with users_shares
    historydata = db.execute(
        "SELECT symbol, ABS(numshares) AS numshares, price, time, transaction_type FROM users_shares WHERE user_id = ?", session['user_id'])

    return render_template("history.html", historydatas=historydata)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Remember amount of cash
        # user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html", login_data=0)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # checks if user uses POST
    if request.method == "POST":

        # if symbol is not returned
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 400)

        req_quotes = request.form.get("symbol")
        quote_results = lookup(req_quotes)

        if str(quote_results) == "None":

            # lookup fails return symbol unavailable
            return apology("must provide a valid quote symbol", 400)

        else:
            # lookup the stock symbol and display results
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
            return render_template("quote_results.html", tabledata=quote_results, cash=cash)

    # checks if user uses GET
    else:
        # display request stock quote template
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        return render_template("quote_form.html", cash=cash)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Checks if user uses POST
    if request.method == "POST":

        # ERROR CHECKS:
        # return apology if fields are blank
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # if password and confirmation don't match, return apology
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # if username is taken, return apology
        name_validation = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))
        print(name_validation)

        if len(name_validation) > 0:
            return apology("username taken", 400)

        # Ensure hashing of password given before stored in database
        hashedpassword = generate_password_hash(request.form.get("password"))

        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), hashedpassword)
        hashedpassword = " "

        # html returned
        return render_template("login.html", login_data={"user": request.form.get("username"), "password": request.form.get("password"), "function": 1})

    # Checks if user uses GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        sell_symbol = request.form.get("symbol")

        # validation
        if not sell_symbol:
            return apology("Must provide symbol", 400)
        if not request.form.get("shares"):
            return apology("Must provide number of shares", 400)

        owned_shares = []
        owned_data_shares = db.execute("SELECT DISTINCT symbol FROM users_shares WHERE user_id = ?", session['user_id'])
        for owned_share in owned_data_shares:
            owned_shares.append(owned_share['symbol'])

        if sell_symbol not in owned_shares:
            return apology("You don't own this share", 400)

        sell_numshare = db.execute(
            "SELECT SUM(numshares) AS num_of_share FROM users_shares WHERE user_id = ? AND symbol = ?", session['user_id'], sell_symbol)
        try:
            if int(request.form.get("shares")) < 1:
                return apology("Must provide a valid number of shares", 400)
            elif int(request.form.get("shares")) > sell_numshare[0]['num_of_share']:
                return apology("You do not own this amount of shares")
        except:
            return apology("Must provide a valid number of shares", 400)

        share_price = float(lookup(sell_symbol)['price'])
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])[0]["cash"]
        total_sell_price = (share_price * int(request.form.get('shares')))  # profit

        time_sold = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE users SET cash = ? WHERE id = ?", round(cash+total_sell_price, 2), session['user_id'])
        db.execute("INSERT INTO users_shares (user_id, symbol, numshares, price, time, newcash, transaction_type) VALUES (?, ?, ?, ?, ?, ?, 'sold')",
                   session['user_id'], sell_symbol, -int(request.form.get("shares")), round(share_price, 2), time_sold, round(cash+total_sell_price, 2))

        return redirect("/")

    # GET
    else:
        shares = []
        for data in db.execute("SELECT symbol, SUM(numshares) AS share_num FROM users_shares GROUP BY symbol, user_id HAVING user_id = ?", session['user_id']):
            if data['share_num'] > 0:
                shares.append(data['symbol'])

        db.execute("DELETE FROM temp_info WHERE user_id = ?", session['user_id'])
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        return render_template("sell_form.html", shares=shares, cash=cash)

