SMSMyBus
========
This project is a civic hacking project that makes the Madison Metro bus system more accessible, 
easier to use, and make the entire riding experience more enjoyable.

https://www.smsmybus.com

The app is currently deployed on Google App Engine.

SMSMyBus Applications
---------------------
The original goal of this project was to provide access to real-time arrival estimates via a 
variety of mobile interfaces:

* SMS
* XMPP (Google Chat)
* Email
* Phone
* Google gadget

Kiosk Displays
--------------
Simple browser-based views of stop traffic can be supported using a kiosk application. 

* public/kiosk/  contains the static displays for Mother Fool's, Sector67 and Supranet
* apps/kiosk/  contains the dynamic display generator that creates a kios for any two stops in the system

SMSMyBus API
------------

Over time, the project evolved into an abstraction over those interfaces and general purpose web 
services were created for accessing schedule, route and location data.

This project once contained the API as well but was split apart to separate the applications. The API project can be found 
at github.com/gregtracy/msn-transit-api. But note that the deployed version of the app is free to use so if you fork and modify
this project, feel free to point at that instance of the API. All you need is a dev key.

https://api.smsmybus.com

