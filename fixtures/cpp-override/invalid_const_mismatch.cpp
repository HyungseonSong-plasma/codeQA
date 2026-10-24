struct Base { virtual void handle() const {} };
struct Child : Base { void handle() override {} };
