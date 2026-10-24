struct Base { void handle(int) {} };
struct Child : Base { void handle(int) override {} };
