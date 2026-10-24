struct Base { virtual int handle() { return 0; } };
struct Child : Base { double handle() override { return 1.0; } };
