import React from "react";
import { Link } from "react-router-dom";
import SignIn from "../sign-in/sign-in.component";
import SignOut from "../sign-out/sign-out.component";
const Navbar = () => {
  return (
    <nav className="nav-wrapper grey darken-3">
      <div className="container">
        <Link to="/" className="brand-logo">
          MarioPlan
        </Link>
        <SignIn />
        <SignOut />
      </div>
    </nav>
  );
};

export default Navbar;
