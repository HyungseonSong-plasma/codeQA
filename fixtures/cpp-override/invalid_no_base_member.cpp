struct Base { virtual void found() {} };
struct Child : Base { void missing() override {} };
