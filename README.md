# diggerweb

This project is the web version of my previous "digger" application. It is a project that I am using to learn some React.js and some Python backend, since it is a topic that I don't usually use at my current job. 

The project will permit users to make some researches inside the Discogs DB using some "smart" parameter, that I would like to have when browsin the application. In addition, I would like to give the users some possiiblity to make faster eresearches on other websites that djs commonly use, like decks.de etc.

# current development status
Currently the project provides a simple backend implementation that permits to make queries on the Discogs DB. The next step is to define a front end page to present the provided data

## how to run

Inside your terminal execute the following commands

```
$ git clone https://github.com/giorgiogamba/diggerweb.git
$ cd diggerweb/backend/diggerweb_backend
$ python manage.py runserver
```
Once the program response a successful server start up, it will provide a link you have to navigate to, and authorize the access of the application to your Discogs account.
Copy the provided code and paste it inside the terminal under "verification code: "

Once you entered the code, the server is ready to responde. 

At this point, you have to start the frontend page to execute queries:

From the project root:
```
$ cd frontend
$ npm run dev
```

The terminal will answer you with a link to a localhost port, something like https://localhost::5173. Enter this code inside a browser and then you will have access to the frontend page.



