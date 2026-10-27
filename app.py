from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = "shhhhhhhcsproject"

#this is for email sending
app.config['MAIL_SERVER'] = 'smtp.gmail.com' 
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'cs321lostandfound@gmail.com' #temp email until i figure out something better
app.config['MAIL_PASSWORD'] = 'msrr vfbe gsby qlfy'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

@app.route("/") #home page
def home():
   return render_template('home.html')

@app.route("/login", methods=['GET', 'POST']) #login page
def login():
   try:
      if request.method == 'POST':
         user = request.form['user'].strip() # takes email from input, for now takes any email
         session["user"] = user #creates a session

         msg = Message("email code", sender='noreply@gmulandf.com', recipients=[user]) #sends email to user
         msg.body = "code is 1234"
         mail.send(msg)
         return redirect(url_for('validate')) # redirects to validate

      if "user" in session: # if already logged in
         return redirect(url_for('mainpage'))

      
      return render_template('login.html') #first time opening page or no input
   
   except Exception as e:
      app.logger.exception("Failed to send email.")
      flash("Failed to send email.", "error")
      return redirect(url_for('login'))

@app.route("/validate", methods=['GET', 'POST'])
def validate():
   if request.method == 'POST':
      code = request.form['code'].strip()
      if code == '1234': #checks if code correct, will be randomized later
         return redirect(url_for('mainpage'))
      
      else: # if code incorrect
         flash("Incorrect code.", "error")
         return redirect(url_for('validate')) 
   
   return render_template('validate.html') # initial opening of page

@app.route("/main") # main page when logged in
def mainpage():
   if "user" in session: # just checks if logged in
      user = session["user"]
      return f"Signed in as {user}"
   
   else: # if not logged in return to login page
      return redirect(url_for('login'))

@app.route("/logout")
def logout():
   if "user" in session:
      session.clear()
      flash("You have been logged out.", "info")
   
   return redirect(url_for('login'))

if __name__ == "__main__":
   app.run(debug=True)