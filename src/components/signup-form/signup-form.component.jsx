import React, { Component } from "react";
import FormInput from "../form-input/form-input.component";
import CustomButton from "../custom-button/custom-button.component";

class SignupForm extends Component {
  state = {
    fisrtName: "",
    lastName: "",
    email: "",
    password: "",
  };

  handleChange = ({ target }) => {
    const name = target.name;
    const value = target.value;
    this.setState({ [name]: value });
  };
  handleSubmit = (e) => {
    e.perventDefault();
    console.log(this.state);
  };
  render() {
    return (
      <form action={this.handleSubmit} className="white">
        <h5 className="grey-text text-darken-3">Sign Up</h5>

        <FormInput
          name="firstName"
          title="First Name"
          type="text"
          value={this.state.fisrtName}
          handleChange={this.handleChange}
        />

        <FormInput
          name="lastName"
          title="Last Name"
          type="text"
          value={this.state.lastName}
          handleChange={this.handleChange}
        />
        <FormInput
          name="email"
          title="Email"
          type="email"
          value={this.state.email}
          handleChange={this.handleChange}
        />
        <FormInput
          name="password"
          title="Password"
          type="password"
          value={this.state.password}
          handleChange={this.handleChange}
        />
        <CustomButton title="sign up" />
      </form>
    );
  }
}

export default SignupForm;
