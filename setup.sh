sudo pip3 install "gql[all]"
sudo cp ./klaxon.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable --now klaxon