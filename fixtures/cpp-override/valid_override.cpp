struct Base { virtual int handle(int) const noexcept { return 0; } };
struct Child : Base { int handle(int) const noexcept override { return 1; } };
int main() { Child c; return c.handle(1); }
