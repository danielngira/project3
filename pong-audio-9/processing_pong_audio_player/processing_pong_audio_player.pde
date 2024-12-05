// PONG PLAYER EXAMPLE

import oscP5.*;
import netP5.*;

OscP5 oscP5;

NetAddress myBroadcastLocation;

String host_ip = "127.0.0.1";
String my_ip = "127.0.0.1";
String player = "p1";

int port_out = 5005;
int port_in = 5007;

void setup() {
  size(400, 400);
  frameRate(25);

  if (player == "p2") {
    port_out = 5006;
    port_in = 5008;
  }

  oscP5 = new OscP5(this, port_in);
  myBroadcastLocation = new NetAddress(host_ip, port_out);

  // connect to host
  OscMessage myOscMessage = new OscMessage("/connect");
  myOscMessage.add(my_ip); // dummy data
  oscP5.send(myOscMessage, myBroadcastLocation);
}

void draw() {
  background(0);
  textSize(20);
  text("your are "+player, 40, 80); 
  text("click in the window to say hi", 40, 120); 
}

void mousePressed() {
  // say hi to opponent!
  OscMessage myOscMessage = new OscMessage("/hi");
  myOscMessage.add(1); // dummy data
  oscP5.send(myOscMessage, myBroadcastLocation);
}

// read game info from host
void oscEvent(OscMessage theOscMessage) {
  /* get and print the address pattern and the typetag of the received OscMessage */
  println("### received an osc message with addrpattern "+theOscMessage.addrPattern()+" and typetag "+theOscMessage.typetag());
  theOscMessage.print();
}
