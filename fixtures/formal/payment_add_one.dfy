method AddOne(x: int) returns (y: int)
  ensures y == x + 1
{
  y := x + 1;
}

method Main()
{
  var result := AddOne(41);
  assert result == 42;
  print result, "\n";
}
