import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # if user reached route via POST
    if request.method == "POST":
        
        prompts = {"firstname": "First Name",
                   "lastname": "Last Name",
                   "username": "Username",
                   "password": "Password",
                   "confirm": "Confirm",
                   "email": "Email Address",
                   "dob": "Date of Birth",
                   "address": "Address",
                   "city": "City",
                   "state": "State",
                   "zip": "Zip Code"}
        
        prompt_vals = {key: request.form.get(key) for key in prompts.keys()}
        
        # if any parameters are unfilled, send user back to the register page
        if min([parameter == "" for parameter in prompt_vals.values()]):
            return render_template("register.html", reminder=True, method="get")
        
        try:
            username_valid = min([prompt_vals["username"] != dictionary["username"]
                              for dictionary in db.execute("SELECT username FROM users")])
        except ValueError:
            username_valid = True
        
        if prompt_vals["password"] == prompt_vals["confirm"] and username_valid:
            
            # hash the password
            hash = pwd_context.hash(str(prompt_vals["password"]))
            
            try:
                last_id = db.execute("SELECT id FROM 'users' ORDER BY id DESC LIMIT 1;")[0]["id"]
            except:
                last_id = 0
            
            db.execute("INSERT INTO 'users' " + \
                       "(id, username, hash, firstname, lastname, email, dob, address, city, state, zip, cash) " + \
                       "VALUES (:id, :username, :hash, :firstname, :lastname, :email, :dob, :address, :city, :state, :zip, 10000);",
                       id=last_id + 1,
                       username=prompt_vals["username"],
                       hash=hash,
                       firstname=prompt_vals["firstname"],
                       lastname=prompt_vals["lastname"],
                       email=prompt_vals["email"],
                       dob=prompt_vals["dob"],
                       address=prompt_vals["address"],
                       city=prompt_vals["city"],
                       state=prompt_vals["state"],
                       zip=prompt_vals["zip"])
             
            # remember which user registers and thus signs in
            rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))          
            session["user_id"] = rows[0]["id"]
                       
            return redirect(url_for("index"))
            
        return render_template("register.html", reminder=True)
    
    # else if user reached route via GET
    else:
        return render_template("register.html", reminder=False)
        
@app.route("/")
@login_required
def index():
    if request.method == "GET":
        stocks_raw = db.execute("SELECT * FROM 'shares' WHERE id = :id", id=session["user_id"])
        
        # Create a new list of stocks, removing duplicates
        stocks = []
        for stock_raw in stocks_raw:
            try:
            
                # if user does not own any of the stock, make a new table row
                if min([stock_raw["symbol"] not in stock.values() for stock in stocks]):
                    stocks.append(stock_raw)
                    
                # otherwise add to existing table rows
                else:
                    for num, stock in enumerate(stocks):
                        if stock["symbol"] == stock_raw["symbol"]:
                            stocks[num]["quantity"] += stock_raw["quantity"]
            
            # error will be raised, meaning this is the first stock and no other stocks are in the stocks list yet
            except ValueError:
                stocks.append(stock_raw)
        
        portfolio_val = 0
        for num, stock in enumerate(stocks):
            # add key value pairs to stocks dictionary based on lookup data
            data = lookup(stock["symbol"])
            stocks[num]["name"] = data["name"]
            stocks[num]["price"] = data["price"]
            stocks[num]["total_price"] = stocks[num]["price"] * stocks[num]["quantity"]
            
            portfolio_val += stocks[num]["total_price"]
            
            # turn into usd once finished with operations
            stocks[num]["price"] = usd(stocks[num]["price"])
            stocks[num]["total_price"] = usd(stocks[num]["total_price"])
        
        user_cash = db.execute("SELECT * FROM 'users' WHERE id = :user_id", user_id=session["user_id"])[0]["cash"]
        
        return render_template("index.html", stocks=stocks, user_cash=usd(user_cash), portfolio_val=usd(portfolio_val + user_cash))
    return apology("Not using the GET method")
        
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # if user reached route via POST
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock_data = lookup(symbol)
        
        if stock_data:
            return render_template("quote.html", price=stock_data["price"], name=stock_data["name"], symbol=stock_data["symbol"],
                                   reminder=False)
        else:
            return render_template("quote.html", reminder=True)
    
    # else if user reached route via GET
    else:
        return render_template("quote.html")
        
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        user_id = session["user_id"]
        user_cash = db.execute("SELECT * FROM 'users' WHERE id = :user_id", user_id=user_id)[0]["cash"]
        
        symbol = request.form.get("symbol").upper()
        try:
            price = lookup(symbol)["price"]
        except TypeError:
            return render_template("buy.html", reminder=True)
        
        quantity = request.form.get("quantity")
        
        if symbol == "" or quantity == "":
            return render_template("buy.html", reminder=True)
        
        try:
            quantity = int(quantity)
            
            if quantity <= 0:
                return render_template("sell.html", reminder=True)
        except ValueError:
            return render_template("sell.html", reminder=True)
        
        total_price = price * quantity
        
        if total_price <= user_cash:
            user_cash -= total_price
            
            # log a transaction
            db.execute("INSERT INTO 'transactions' " + \
                       "(id, type, symbol, quantity, price) " + \
                       "VALUES (:id, :type, :symbol, :quantity, :price)",
                       id=user_id,
                       type="buy",
                       symbol=symbol,
                       quantity=quantity,
                       price=price)
                 
            rows = db.execute("SELECT * FROM 'shares' WHERE id = :id AND symbol = :symbol",
                              id=user_id,
                              symbol=symbol)
                              
            # if user doesn't own any stock from this company, add a new row to the table
            if len(rows) == 0:
                db.execute("INSERT INTO 'shares' " + \
                           "(id, symbol, quantity) " + \
                           "VALUES (:id, :symbol, :quantity)",
                           id=user_id,
                           symbol=symbol,
                           quantity=quantity)
            
            # else user already owns stocks from this company, increment value  
            else:
                db.execute("UPDATE 'shares' SET quantity = :quantity WHERE id = :id AND symbol = :symbol",
                           id=user_id,
                           symbol=symbol,
                           quantity=rows[0]["quantity"] + quantity)
            
            
            # if users already owns stocks from this company, increment value
            
            # change the user's cash
            db.execute("UPDATE 'users' SET cash = :cash WHERE id = :id", cash=user_cash, id=user_id)
            
            # go back to the index page
            flash("Bought!")
            return redirect(url_for("index"))
        
        else:
            return render_template("buy.html", reminder=True)
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        pass
    return render_template("buy.html", reminder=False)

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        user_id = session["user_id"]
        user_cash = db.execute("SELECT * FROM 'users' WHERE id = :user_id", user_id=user_id)[0]["cash"]
        
        symbol = request.form.get("symbol").upper()
        try:
            price = lookup(symbol)["price"]
        except TypeError:
            return render_template("sell.html", reminder=True)
        
        quantity = request.form.get("quantity")
        
        if symbol == "" or quantity == "":
            return render_template("sell.html", reminder=True)
        
        try:
            quantity = int(quantity)
            
            if quantity <= 0:
                return render_template("sell.html", reminder=True)
        except ValueError:
            return render_template("sell.html", reminder=True)
            
        total_price = price * quantity
        
        rows = db.execute("SELECT * FROM 'shares' WHERE id = :id AND symbol = :symbol",
                              id=user_id,
                              symbol=symbol)
        
        try:
            owned_quantity = rows[0]["quantity"]
        except:
            return render_template("sell.html", reminder=True)
        
        if quantity <= owned_quantity:
            user_cash += total_price
            
            # log a transaction
            db.execute("INSERT INTO 'transactions' " + \
                       "(id, type, symbol, quantity, price) " + \
                       "VALUES (:id, :type, :symbol, :quantity, :price)",
                       id=user_id,
                       type="sell",
                       symbol=symbol,
                       quantity=quantity,
                       price=price)
                 
            # if user owns more than is selling, update the quantity
            if quantity < owned_quantity:
                db.execute("UPDATE 'shares' SET quantity = :quantity WHERE id = :id AND symbol = :symbol",
                          id=user_id,
                          symbol=symbol,
                          quantity=owned_quantity - quantity)
            
            else:
                db.execute("DELETE FROM 'shares' WHERE id = :id AND symbol = :symbol",
                           id=user_id,
                           symbol=symbol)
            
            # change the user's cash
            db.execute("UPDATE 'users' SET cash = :cash WHERE id = :id", cash=user_cash, id=session["user_id"])
            
            # go back to the index page
            flash("Sold!")
            return redirect(url_for("index"))
        
        else:
            return render_template("sell.html", reminder=True)
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        pass
    return render_template("sell.html", reminder=False)
    
@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    transactions = db.execute("SELECT * FROM 'transactions' WHERE id = :id", id=session["user_id"])
    
    for num, transaction in enumerate(transactions):
        data = lookup(transaction["symbol"])
        transactions[num]["type"] = transactions[num]["type"][0].upper() + transactions[num]["type"][1:]
        transactions[num]["name"] = data["name"]
    
    return render_template("history.html", transactions=transactions)
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)