main()
 ├── read_config()
 ├── start run_server() thread
 │     └── bind → listen → accept
 ├── start run_client() thread
 │     └── connect → send initial UUID
 ├── wait for both threads
 └── receive_loop()
       └── receive → compare → forward/ignore → elect leader

Data received and sent is a JSON containing: 
the unique universal identifier (uuid) 
and the flag for if the received uuid is the leader (0 = not elected, 1 = elected)

Example of data received:
data = {
    "uuid": "abcdef...."
    "flag": 0
}