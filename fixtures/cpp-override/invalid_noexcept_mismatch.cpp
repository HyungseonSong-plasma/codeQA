struct Base { virtual void handle() noexcept {} };
struct Child : Base { void handle() override {} };
