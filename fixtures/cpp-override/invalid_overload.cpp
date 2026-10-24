struct Base { virtual void handle(int) {} };
struct Child : Base { void handle(double) override {} };
