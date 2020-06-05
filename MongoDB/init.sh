mongo <<EOF
    use scheduling_service
    db.createUser({user: 'scheduling_service', pwd: 'scheduling_service_pwd', roles: [ 'readWrite' ]})
EOF
