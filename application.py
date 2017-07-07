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

@app.route("/")
@login_required
def index():
    stockSymbols = db.execute("SELECT symbol FROM transactions WHERE user_id=:user_id GROUP BY symbol;", user_id=session["user_id"])
    grandTotal = 0

    if stockSymbols != []:
        stocks = []
        cashBalance = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=session["user_id"])
        
        for symbol in stockSymbols:
            symbolInfo = lookup(symbol['symbol'])
            stockShares = db.execute("SELECT SUM(shares) FROM transactions WHERE user_id=:user_id AND symbol=:symbol;", user_id=session['user_id'], symbol=symbolInfo['symbol'])
            
            if stockShares[0]['SUM(shares)'] > 0:
                stockInfo = {}
                stockInfo['name'] = symbolInfo['name']
                stockInfo['symbol'] = symbolInfo['symbol']
                stockInfo['price'] = symbolInfo['price']
                stockInfo['shares'] = stockShares[0]['SUM(shares)']
                stockInfo['total'] = stockInfo['shares'] * stockInfo['price']
                stocks.append(stockInfo)
            
            else:
                continue
                
        for i in range(len(stocks)):
            grandTotal += stocks[i]['total']
            stocks[i]['price'] = usd(stocks[i]['price'])
            stocks[i]['total'] = usd(stocks[i]['total'])
        
        grandTotal += cashBalance[0]['cash']
        grandTotal = usd(grandTotal)
        cashBalance=usd(cashBalance[0]['cash'])
        return render_template("index.html", cashBalance=cashBalance, grandTotal=grandTotal, stocks=stocks)
        
    else:
        cashBalance = db.execute("SELECT cash FROM users WHERE id=:user_id;", user_id=session['user_id'])
        grandTotal = usd(grandTotal)
        cashBalance=usd(cashBalance[0]['cash'])
        return render_template("index.html", cashBalance=cashBalance, grandTotal=grandTotal)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        try:
            symbol = lookup(request.form.get("symbol"))
            shares = int(request.form.get("shares"))
        except:
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="No input.")
            
        if not symbol:
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="Invalid symbol.")
            
        if not shares or shares <= 0:
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="Please provide a valid number of shares.")
            
        cashBalance = db.execute("SELECT cash FROM users WHERE id=:user_id;", user_id=session["user_id"])
        cashBalance = int(cashBalance[0]['cash'])
        price = symbol['price']
        totalPrice = shares*price
        
        if totalPrice < cashBalance:
            db.execute("INSERT INTO transactions (symbol, shares, price, user_id) VALUES (:symbol, :shares, :price, :user_id);", symbol=symbol['symbol'], shares=shares, price=symbol['price'], user_id=session['user_id'])
            db.execute("UPDATE users SET cash=(cash-:totalPrice) WHERE id=:user_id;", user_id=session["user_id"], totalPrice=totalPrice)
            return render_template("success.html", alert="BOUGHT!", explain="Stocks successfully bought.")
        
        else:
            return render_template("sorry.html", alert="Haha, peasant.", explain="You do not have enough money in your cash balance.")
    
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    stocks = db.execute("SELECT symbol, shares, price, date_time FROM transactions WHERE user_id=:user_id", user_id=session['user_id'])

    for stock in stocks:
        stock['price'] = usd(stock['price'])

    return render_template("history.html", stock=stock, stocks=stocks)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return render_template("sorry.html", alert="No username!", explain="Please provide a username.")

        # ensure password was submitted
        elif not request.form.get("password"):
            return render_template("sorry.html", alert="No password!", explain="Please provide a password.")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="Invalid username/password.")

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

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
        if request.method == "POST":
            quote = lookup(request.form.get("symbol"))
            if not quote:
                return render_template("sorry.html", alert="Unsuccessful attempt", explain="Invalid stock symbol.")
            else:
                quote['price'] = usd(quote['price'])
                return render_template("quoted.html", quote=quote)
                
        else:
            return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    
    if request.method == "POST":
        
        if not request.form.get("username"):
            return render_template("sorry.html", alert="Unsuccessful registration", explain="Please provide a username.")

        if not request.form.get("password"):
            return render_template("sorry.html", alert="Unsuccessful registration", explain="Please provide a password.")
            
        if not request.form.get("confirmation"):
            return render_template("sorry.html", alert="Unsuccessful registration", explain="Please provide a password confirmation.")
        
        pass1 = request.form.get("password")
        pass2 = request.form.get("confirmation")
        if pass1 != pass2:
            return render_template("sorry.html", alert="Unsuccessful registration", explain="Password and confirmation do not match.")
        
        hash = pwd_context.hash(request.form.get("password"))
        
        registerDone = db.execute("INSERT INTO users (username,hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=hash)
        if not registerDone:
            return apology ("please choose a different username")

        user_id = db.execute("SELECT id FROM users WHERE username=:username", username=request.form.get("username"))
        session["user_id"] = user_id[0]["id"]
        return render_template("success.html", alert="REGISTERED!", explain="Successfully registered as a new user.")
        
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        try:
            symbol = lookup(request.form.get("symbol"))
            shares = int(request.form.get("shares"))
        except:
            return render_template("sorry.html", alert="No input", explain=" ")
            
        if not symbol:
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="Please input a valid symbol.")
            
        if not shares or shares <= 0:
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="Please provide number of shares.")
            
        stocksOwned = db.execute("SELECT SUM(shares) FROM transactions WHERE user_id=:user_id AND symbol=:symbol;", user_id=session['user_id'], symbol=symbol['symbol'])
        
        if not stocksOwned[0]['SUM(shares)'] :
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="No stocks owned.")
            
        if shares > stocksOwned[0]['SUM(shares)']:
            return render_template("sorry.html", alert="Unsuccessful attempt", explain="Not enough stocks owned.")
            
        db.execute("INSERT INTO transactions (symbol, shares, price, user_id) VALUES (:symbol, :shares, :price, :user_id);", symbol=symbol['symbol'], shares=-shares, price=symbol['price'], user_id=session["user_id"])
        db.execute("UPDATE users SET cash=cash+:totalPrice WHERE id=:user_id;", user_id=session['user_id'], totalPrice=shares*symbol['price'])
        
        return render_template("success.html", alert="SOLD!", explain="Stocks successfully sold.")
        
    else:
        return render_template("sell.html")
        
# personal touch    
@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        try:
            deposit = int(request.form.get("deposit"))
        except:
            return render_template("sorry.html", alert="Unsuccessful deposit", explain="No input.")
            
        if deposit <= 0:
            return render_template("sorry.html", alert="Unsuccessful deposit", explain="Please provide a valid number of shares.")

        cashBalance = db.execute("SELECT cash FROM users WHERE id=:user_id;", user_id=session["user_id"])
        cashBalance = int(cashBalance[0]['cash'])
        
        db.execute("UPDATE users SET cash=cash+:deposit WHERE id=:user_id;", user_id=session["user_id"], deposit=deposit)
        return render_template("success.html", alert="DEPOSITED!", explain="Money successfully deposited into account.")
    
    else:
        return render_template("deposit.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)