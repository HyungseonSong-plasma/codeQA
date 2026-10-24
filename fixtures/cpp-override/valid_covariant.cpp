struct Base { virtual Base* clone() const { return nullptr; } };
struct Derived : Base { Derived* clone() const override { return nullptr; } };
int main() { Derived d; return d.clone() == nullptr ? 0 : 1; }
